# coding=utf-8
from __future__ import absolute_import, division
from collections import namedtuple
from datetime import date, datetime, timedelta

from django.contrib.humanize.templatetags.humanize import naturaltime
from django.urls import reverse
from django.utils.translation import ugettext_noop, ugettext as _, ugettext_lazy

from casexml.apps.phone.analytics import get_sync_logs_for_user
from casexml.apps.phone.models import SyncLogAssertionError
from couchdbkit import ResourceNotFound
from corehq.apps.es.aggregations import DateHistogram
from corehq.apps.hqwebapp.decorators import use_nvd3
from couchexport.export import SCALAR_NEVER_WAS

from corehq.apps.reports.filters.users import LocationRestrictedMobileWorkerFilter, ExpandedMobileWorkerFilter
from corehq.apps.es import filters
from dimagi.utils.dates import safe_strftime
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import string_to_utc_datetime
from phonelog.models import UserErrorEntry

from corehq import toggles
from corehq.apps.app_manager.dbaccessors import get_app, get_brief_apps_in_domain
from corehq.apps.es import UserES
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import user_display_string
from corehq.const import USER_DATE_FORMAT
from corehq.util.couch import get_document_or_404

from corehq.apps.locations.permissions import location_safe
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.filters.select import SelectApplicationFilter
from corehq.apps.reports.generic import GenericTabularReport, GetParamsMixin, PaginatedReportMixin
from corehq.apps.reports.standard import ProjectReportParametersMixin, ProjectReport
from corehq.apps.reports.util import format_datatables_data
from corehq.util.quickcache import quickcache


class DeploymentsReport(GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
    Base class for all deployments reports
    """


@location_safe
class ApplicationStatusReport(GetParamsMixin, PaginatedReportMixin, DeploymentsReport):
    name = ugettext_noop("Application Status")
    slug = "app_status"
    emailable = True
    exportable = True
    exportable_all = True
    ajax_pagination = True
    fields = [
        'corehq.apps.reports.filters.users.LocationRestrictedMobileWorkerFilter',
        'corehq.apps.reports.filters.select.SelectApplicationFilter'
    ]
    primary_sort_prop = None

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Username"), prop_name='username.exact'),
            DataTablesColumn(_("Last Submission"),
                             prop_name='reporting_metadata.last_submissions.submission_date',
                             alt_prop_name='reporting_metadata.last_submission_for_user.submission_date'),
            DataTablesColumn(_("Last Sync"),
                             prop_name='reporting_metadata.last_syncs.sync_date',
                             alt_prop_name='reporting_metadata.last_sync_for_user.sync_date'),
            DataTablesColumn(_("Application"),
                             help_text=_("The name of the application from the user's last request."),
                             sortable=False),
            DataTablesColumn(_("Application Version"),
                             help_text=_("The application version from the user's last request."),
                             prop_name='reporting_metadata.last_builds.build_version',
                             alt_prop_name='reporting_metadata.last_build_for_user.build_version'),
            DataTablesColumn(_("CommCare Version"),
                             help_text=_("""The CommCare version from the user's last request"""),
                             prop_name='reporting_metadata.last_submissions.commcare_version',
                             alt_prop_name='reporting_metadata.last_submission_for_user.commcare_version'),
        )
        headers.custom_sort = [[1, 'desc']]
        return headers

    @property
    def default_sort(self):
        if self.selected_app_id:
            self.primary_sort_prop = 'reporting_metadata.last_submissions.submission_date'
            return {
                self.primary_sort_prop: {
                    'order': 'desc',
                    'nested_filter': {
                        'term': {
                            self.sort_filter: self.selected_app_id
                        }
                    }
                }
            }
        else:
            self.primary_sort_prop = 'reporting_metadata.last_submission_for_user.submission_date'
            return {'reporting_metadata.last_submission_for_user.submission_date': 'desc'}

    @property
    def sort_base(self):
        return '.'.join(self.primary_sort_prop.split('.')[:2])

    @property
    def sort_filter(self):
        return self.sort_base + '.app_id'

    def get_sorting_block(self):
        sort_prop_name = 'prop_name' if self.selected_app_id else 'alt_prop_name'
        res = []
        #the NUMBER of cols sorting
        sort_cols = int(self.request.GET.get('iSortingCols', 0))
        if sort_cols > 0:
            for x in range(sort_cols):
                col_key = 'iSortCol_%d' % x
                sort_dir = self.request.GET['sSortDir_%d' % x]
                col_id = int(self.request.GET[col_key])
                col = self.headers.header[col_id]
                sort_prop = getattr(col, sort_prop_name) or col.prop_name
                if x == 0:
                    self.primary_sort_prop = sort_prop
                if self.selected_app_id:
                    sort_dict = {
                        sort_prop: {
                            "order": sort_dir,
                            "nested_filter": {
                                "term": {
                                    self.sort_filter: self.selected_app_id
                                }
                            }
                        }
                    }
                else:
                    sort_dict = {sort_prop: sort_dir}
                res.append(sort_dict)
        if len(res) == 0 and self.default_sort is not None:
            res.append(self.default_sort)
        return res

    @property
    @memoized
    def selected_app_id(self):
        return self.request_params.get(SelectApplicationFilter.slug, None)

    @quickcache(['app_id'], timeout=60 * 60)
    def get_app_name(self, app_id):
        try:
            app = get_app(self.domain, app_id)
        except ResourceNotFound:
            pass
        else:
            return app.name

    def get_data_for_app(self, options, app_id):
        try:
            data = filter(lambda option: option['app_id'] == app_id,
                          options)[0]
            return data
        except IndexError:
            return {}

    @memoized
    def user_query(self, pagination=True):
        mobile_user_and_group_slugs = set(
            self.request.GET.getlist(LocationRestrictedMobileWorkerFilter.slug) +
            self.request.GET.getlist(ExpandedMobileWorkerFilter.slug)  # Cater for old ReportConfigs
        )
        user_query = LocationRestrictedMobileWorkerFilter.user_es_query(
            self.domain,
            mobile_user_and_group_slugs,
        )
        user_query = (user_query
                      .set_sorting_block(self.get_sorting_block()))
        if pagination:
            user_query = (user_query
                          .size(self.pagination.count)
                          .start(self.pagination.start))
        if self.selected_app_id:
            user_query = user_query.nested(
                self.sort_base,
                filters.term(self.sort_filter, self.selected_app_id)
            )
        return user_query

    def process_rows(self, users, fmt_for_export=False):
        rows = []
        for user in users:
            last_build = last_seen = last_sub = last_sync = last_sync_date = app_name = commcare_version = None
            build_version = _("Unknown")
            reporting_metadata = user.get('reporting_metadata', {})
            if self.selected_app_id:
                last_submissions = reporting_metadata.get('last_submissions')
                if last_submissions:
                    last_sub = self.get_data_for_app(last_submissions, self.selected_app_id)
                last_syncs = reporting_metadata.get('last_syncs')
                if last_syncs:
                    last_sync = self.get_data_for_app(last_syncs, self.selected_app_id)
                    if last_sync is None:
                        last_sync = self.get_data_for_app(last_syncs, None)
                last_builds = reporting_metadata.get('last_builds')
                if last_builds:
                    last_build = self.get_data_for_app(last_builds, self.selected_app_id)
            else:
                last_sub = reporting_metadata.get('last_submission_for_user', {})
                last_sync = reporting_metadata.get('last_sync_for_user', {})
                last_build = reporting_metadata.get('last_build_for_user', {})
            if last_sub and last_sub.get('commcare_version'):
                commcare_version = _get_commcare_version(last_sub.get('commcare_version'))
            else:
                devices = user.get('devices', None)
                if devices:
                    device = max(devices, key=lambda dev: dev['last_used'])
                    if device.get('commcare_version', None):
                        commcare_version = _get_commcare_version(device.commcare_version)
            if last_sub and last_sub.get('submission_date'):
                last_seen = string_to_utc_datetime(last_sub['submission_date'])
            if last_sync and last_sync.get('sync_date'):
                last_sync_date = string_to_utc_datetime(last_sync['sync_date'])
            if last_build:
                build_version = last_build.get('build_version') or build_version
                if last_build.get('app_id'):
                    app_name = self.get_app_name(last_build['app_id'])
            rows.append([
                user_display_string(user.get('username', ''),
                                    user.get('first_name', ''),
                                    user.get('last_name', '')),
                _fmt_date(last_seen, fmt_for_export), _fmt_date(last_sync_date, fmt_for_export),
                app_name or "---", build_version, commcare_version or '---'
            ])
        return rows

    @property
    def total_records(self):
        if self._total_records:
            return self._total_records
        else:
            return 0

    @property
    def rows(self):
        users = self.user_query().run()
        self._total_records = users.total
        return self.process_rows(users.hits)

    @property
    def get_all_rows(self):
        users = self.user_query(False).scroll()
        return self.process_rows(users, True)

    @property
    def export_table(self):
        def _fmt_timestamp(timestamp):
            if timestamp is not None and timestamp >= 0:
                return safe_strftime(date.fromtimestamp(timestamp), USER_DATE_FORMAT)
            return SCALAR_NEVER_WAS

        result = super(ApplicationStatusReport, self).export_table
        table = result[0][1]
        for row in table[1:]:
            # Last submission
            row[1] = _fmt_timestamp(row[1])
            # Last sync
            row[2] = _fmt_timestamp(row[2])
        return result


def _get_commcare_version(app_version_info):
    commcare_version = (
        'CommCare {}'.format(app_version_info)
        if app_version_info
        else _("Unknown CommCare Version")
    )
    return commcare_version


def _choose_latest_version(*app_versions):
    """
    Chooses the latest version from a list of AppVersion objects - choosing the first one passed
    in with the highest version number.
    """
    usable_versions = filter(None, app_versions)
    if usable_versions:
        return sorted(usable_versions, key=lambda v: v.build_version)[-1]


class SyncHistoryReport(DeploymentsReport):
    DEFAULT_LIMIT = 10
    MAX_LIMIT = 1000
    name = ugettext_noop("User Sync History")
    slug = "sync_history"
    emailable = True
    fields = ['corehq.apps.reports.filters.users.AltPlaceholderMobileWorkerFilter']

    @property
    def report_subtitles(self):
        return [_('Shows the last (up to) {} times a user has synced.').format(self.limit)]

    @property
    def disable_pagination(self):
        return self.limit == self.DEFAULT_LIMIT

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Sync Date"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("# of Cases"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Sync Duration"), sort_type=DTSortType.NUMERIC)
        )
        if self.show_extra_columns:
            headers.add_column(DataTablesColumn(_("Sync Log")))
            headers.add_column(DataTablesColumn(_("Sync Log Type")))
            headers.add_column(DataTablesColumn(_("Previous Sync Log")))
            headers.add_column(DataTablesColumn(_("Error Info")))
            headers.add_column(DataTablesColumn(_("State Hash")))
            headers.add_column(DataTablesColumn(_("Last Submitted")))
            headers.add_column(DataTablesColumn(_("Last Cached")))

        headers.custom_sort = [[0, 'desc']]
        return headers

    @property
    def rows(self):
        base_link_url = '{}?id={{id}}'.format(reverse('raw_couch'))

        user_id = self.request.GET.get('individual')
        if not user_id:
            return []

        # security check
        get_document_or_404(CommCareUser, self.domain, user_id)

        def _sync_log_to_row(sync_log):
            def _fmt_duration(duration):
                if isinstance(duration, int):
                    return format_datatables_data(
                        '<span class="{cls}">{text}</span>'.format(
                            cls=_bootstrap_class(duration or 0, 60, 20),
                            text=_('{} seconds').format(duration),
                        ),
                        duration
                    )
                else:
                    return format_datatables_data(
                        '<span class="label label-default">{text}</span>'.format(
                            text=_("Unknown"),
                        ),
                        -1,
                    )

            def _fmt_id(sync_log_id):
                href = base_link_url.format(id=sync_log_id)
                return '<a href="{href}" target="_blank">{id:.5}...</a>'.format(
                    href=href,
                    id=sync_log_id
                )

            def _fmt_error_info(sync_log):
                if not sync_log.had_state_error:
                    return u'<span class="label label-success">&#10003;</span>'
                else:
                    return (u'<span class="label label-danger">X</span>'
                            u'State error {}<br>Expected hash: {:.10}...').format(
                        _naturaltime_with_hover(sync_log.error_date),
                        sync_log.error_hash,
                    )

            def _get_state_hash_display(sync_log):
                try:
                    return u'{:.10}...'.format(sync_log.get_state_hash())
                except SyncLogAssertionError as e:
                    return _(u'Error computing hash! {}').format(e)

            num_cases = sync_log.case_count()
            columns = [
                _fmt_date(sync_log.date),
                format_datatables_data(num_cases, num_cases),
                _fmt_duration(sync_log.duration),
            ]
            if self.show_extra_columns:
                columns.append(_fmt_id(sync_log.get_id))
                columns.append(sync_log.log_format)
                columns.append(_fmt_id(sync_log.previous_log_id) if sync_log.previous_log_id else '---')
                columns.append(_fmt_error_info(sync_log))
                columns.append(_get_state_hash_display(sync_log))
                columns.append(_naturaltime_with_hover(sync_log.last_submitted))
                columns.append(u'{}<br>{:.10}'.format(_naturaltime_with_hover(sync_log.last_cached),
                                                      sync_log.hash_at_last_cached))

            return columns

        return [_sync_log_to_row(sync_log)
                for sync_log in get_sync_logs_for_user(user_id, self.limit)]

    @property
    def show_extra_columns(self):
        return self.request.user and toggles.SUPPORT.enabled(self.request.user.username)

    @property
    def limit(self):
        try:
            return min(self.MAX_LIMIT, int(self.request.GET.get('limit', self.DEFAULT_LIMIT)))
        except ValueError:
            return self.DEFAULT_LIMIT


def _get_sort_key(date):
    if not date:
        return -1
    else:
        return int(date.strftime("%s"))


def _fmt_date(date, include_sort_key=True):
    def _timedelta_class(delta):
        return _bootstrap_class(delta, timedelta(days=7), timedelta(days=3))

    if not date:
        text = u'<span class="label label-default">{0}</span>'.format(_("Never"))
    else:
        text = u'<span class="{cls}">{text}</span>'.format(
                cls=_timedelta_class(datetime.utcnow() - date),
                text=_(_naturaltime_with_hover(date)),
        )
    if include_sort_key:
        return format_datatables_data(text, _get_sort_key(date))
    else:
        return text


def _naturaltime_with_hover(date):
    return u'<span title="{}">{}</span>'.format(date, naturaltime(date) or '---')


def _bootstrap_class(obj, severe, warn):
    """
    gets a bootstrap class for an object comparing to thresholds.
    assumes bigger is worse and default is good.
    """
    if obj > severe:
        return "label label-danger"
    elif obj > warn:
        return "label label-warning"
    else:
        return "label label-success"


class ApplicationErrorReport(GenericTabularReport, ProjectReport):
    name = ugettext_noop("Application Error Report")
    slug = "application_error"
    ajax_pagination = True
    sortable = False
    fields = ['corehq.apps.reports.filters.select.SelectApplicationFilter']

    # Filter parameters to pull from the URL
    model_fields_to_url_params = [
        ('app_id', SelectApplicationFilter.slug),
        ('version_number', 'version_number'),
    ]

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return user and toggles.APPLICATION_ERROR_REPORT.enabled(user.username)

    @property
    def shared_pagination_GET_params(self):
        shared_params = super(ApplicationErrorReport, self).shared_pagination_GET_params
        shared_params.extend([
            {'name': param, 'value': self.request.GET.get(param, None)}
            for model_field, param in self.model_fields_to_url_params
        ])
        return shared_params

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("User")),
            DataTablesColumn(_("Expression")),
            DataTablesColumn(_("Message")),
            DataTablesColumn(_("Session")),
            DataTablesColumn(_("Application")),
            DataTablesColumn(_("App version")),
            DataTablesColumn(_("Date")),
        )

    @property
    @memoized
    def _queryset(self):
        qs = UserErrorEntry.objects.filter(domain=self.domain)
        for model_field, url_param in self.model_fields_to_url_params:
            value = self.request.GET.get(url_param, None)
            if value:
                qs = qs.filter(**{model_field: value})
        return qs

    @property
    def total_records(self):
        return self._queryset.count()

    @property
    @memoized
    def _apps_by_id(self):
        def link(app):
            return u'<a href="{}">{}</a>'.format(
                reverse('view_app', args=[self.domain, app.get_id]),
                app.name,
            )
        return {
            app.get_id: link(app)
            for app in get_brief_apps_in_domain(self.domain)
        }

    def _ids_to_users(self, user_ids):
        users = (UserES()
                 .domain(self.domain)
                 .user_ids(user_ids)
                 .values('_id', 'username', 'first_name', 'last_name'))
        return {
            u['_id']: user_display_string(u['username'], u['first_name'], u['last_name'])
            for u in users
        }

    @property
    def rows(self):
        start = self.pagination.start
        end = start + self.pagination.count
        errors = self._queryset.order_by('-date')[start:end]
        users = self._ids_to_users({e.user_id for e in errors if e.user_id})
        for error in errors:
            yield [
                users.get(error.user_id, error.user_id),
                error.expr,
                error.msg,
                error.session,
                self._apps_by_id.get(error.app_id, error.app_id),
                error.version_number,
                str(error.date),
            ]


@location_safe
class AggregateAppStatusReport(ProjectReport, ProjectReportParametersMixin):
    slug = 'aggregate_user_status'

    report_template_path = "reports/async/aggregate_user_status.html"
    name = ugettext_lazy("Aggregate User Status")
    description = ugettext_lazy("See the last activity of your project's users in aggregate.")

    fields = [
        'corehq.apps.reports.filters.users.LocationRestrictedMobileWorkerFilter',
    ]
    exportable = False
    emailable = False
    js_scripts = ['reports/js/aggregate_user_status.js']

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return domain and toggles.AGGREGATE_USER_STATUS_REPORT.enabled(domain)

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(AggregateAppStatusReport, self).decorator_dispatcher(request, *args, **kwargs)

    @memoized
    def user_query(self):
        # partially inspired by ApplicationStatusReport.user_query
        mobile_user_and_group_slugs = set(
            self.request.GET.getlist(LocationRestrictedMobileWorkerFilter.slug)
        )
        user_query = LocationRestrictedMobileWorkerFilter.user_es_query(
            self.domain,
            mobile_user_and_group_slugs,
        )
        user_query = user_query.size(0)
        user_query = user_query.aggregations([
            DateHistogram('last_submission', 'reporting_metadata.last_submission_for_user.submission_date', '1d'),
            DateHistogram('last_sync', 'reporting_metadata.last_sync_for_user.sync_date', '1d')
        ])
        return user_query

    @property
    def template_context(self):

        class BucketSeries(namedtuple('Bucket', 'data_series total_series total')):
            @property
            @memoized
            def percent_series(self):
                def _pct(val, total):
                    return (100. * float(val) / float(total)) if total else 0

                return [
                    {
                        'series': 0,
                        'x': row['x'],
                        'y': _pct(row['y'], self.total)
                    }
                    for row in self.total_series
                ]

            def get_summary_data(self):
                def _readable_pct_from_total(total_series, index):
                    return '{0:.0f}%'.format(total_series[index - 1]['y'])

                return [
                    [_readable_pct_from_total(self.percent_series, 3), _('in the last 3 days')],
                    [_readable_pct_from_total(self.percent_series, 7), _('in the last week')],
                    [_readable_pct_from_total(self.percent_series, 30), _('in the last 30 days')],
                    [_readable_pct_from_total(self.percent_series, 60), _('in the last 60 days')],
                ]

        query = self.user_query().run()
        aggregations = query.aggregations
        last_submission_buckets = aggregations[0].raw_buckets
        last_sync_buckets = aggregations[1].raw_buckets
        total_users = query.total

        def _buckets_to_series(buckets):
            # start with N days of empty data
            # add bucket info to the data series
            # add last bucket
            days_of_history = 60
            vals = {
                i: 0 for i in range(days_of_history)
            }
            extra = total = running_total = 0
            today = datetime.today().date()
            for bucket_val in buckets:
                bucket_date = datetime.fromtimestamp(bucket_val['key'] / 1000.0).date()
                delta_days = (today - bucket_date).days
                val = bucket_val['doc_count']
                if delta_days in vals:
                    vals[delta_days] += val
                else:
                    extra += val
                total += val

            daily_series = []
            running_total_series = []

            for i in range(days_of_history):
                running_total += vals[i]
                daily_series.append(
                    {
                        'series': 0,
                        'x': '{}'.format(today - timedelta(days=i)),
                        'y': vals[i]
                    }
                )
                running_total_series.append(
                    {
                        'series': 0,
                        'x': '{}'.format(today - timedelta(days=i)),
                        'y': running_total
                    }
                )

            # catchall / last row
            daily_series.append(
                {
                    'series': 0,
                    'x': 'more than {} days ago'.format(days_of_history),
                    'y': extra,
                }
            )
            running_total_series.append(
                {
                    'series': 0,
                    'x': 'more than {} days ago'.format(days_of_history),
                    'y': running_total + extra,
                }
            )
            return BucketSeries(daily_series, running_total_series, total)

        submission_series = _buckets_to_series(last_submission_buckets)
        sync_series = _buckets_to_series(last_sync_buckets)
        return {
            'last_submission_data': {
                'key': _('Count of Users'),
                'values': submission_series.data_series,
                'color': '#004abf',
            },
            'last_submission_totals': {
                'key': _('Percent of Users'),
                'values': submission_series.percent_series,
                'color': '#004abf',
            },
            'last_sync_data': {
                'key': _('Count of Users'),
                'values': sync_series.data_series,
                'color': '#f58220',
            },
            'last_sync_totals': {
                'key': _('Percent of Users'),
                'values': sync_series.percent_series,
                'color': '#f58220',
            },
            'total_users': total_users,
            'ever_submitted': submission_series.total,
            'ever_synced': sync_series.total,
            'submission_summary': submission_series.get_summary_data(),
            'sync_summary': sync_series.get_summary_data(),
        }
