from corehq.apps.es import UserES, users, queries
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.toggles import RESTRICT_LOGIN_AS
from corehq.util.couch import stale_ok


def update_analytics_indexes():
    """
    Mostly for testing; wait until analytics data sources are up to date
    so that calls to analytics functions return up-to-date

    (modeled very closely after the same function in couchforms.analytics)
    """
    CommCareUser.get_db().view('users/by_domain', limit=1).all()
    get_es_new().indices.refresh(USER_INDEX_INFO.index)


def get_count_of_active_commcare_users_in_domain(domain):
    return _get_count_of_commcare_users_in_domain('active', domain)


def get_count_of_inactive_commcare_users_in_domain(domain):
    return _get_count_of_commcare_users_in_domain('inactive', domain)


def _get_count_of_commcare_users_in_domain(active_flag, domain):
    result = CommCareUser.get_db().view(
        'users/by_domain',
        startkey=[active_flag, domain, 'CommCareUser'],
        endkey=[active_flag, domain, 'CommCareUser', {}],
        group=True,
        group_level=2,
        stale=stale_ok(),
    ).one()
    return result['value'] if result else 0


def get_active_commcare_users_in_domain(domain, start_at=0, limit=None):
    return _get_commcare_users_in_domain('active', domain, start_at, limit)


def get_inactive_commcare_users_in_domain(domain, start_at=0, limit=None):
    return _get_commcare_users_in_domain('inactive', domain, start_at, limit)


def _get_commcare_users_in_domain(active_flag, domain, start_at, limit):
    extra_args = {}
    if start_at != 0:
        extra_args['skip'] = start_at
    if limit is not None:
        extra_args['limit'] = limit
    return CommCareUser.view("users/by_domain",
        reduce=False,
        include_docs=True,
        startkey=[active_flag, domain, 'CommCareUser'],
        endkey=[active_flag, domain, 'CommCareUser', {}],
        stale=stale_ok(),
        **extra_args
    ).all()


def get_search_users_in_domain_es_query(domain, search_string, limit, offset):
    """
    returns a UserES object
    :param domain:
    :param search_string: A query string that searches in the specified search fields
    :param limit: Number of records to return
    :param offset: Offset to start query
    """
    default_search_fields = ["base_username", "last_name", "first_name"]

    user_es = UserES().domain(domain)

    if RESTRICT_LOGIN_AS.enabled(domain):
        user_es = user_es.OR(users.metadata('login_as_user', search_string),
                             queries.search_string_query(search_string, default_search_fields))
    else:
        user_es = user_es.search_string_query(search_string, default_search_fields)

    return user_es.start(offset).size(limit).sort('username.exact')


def get_role_user_count(domain, role_id):
    from corehq.apps.es.users import UserES
    return UserES().is_active().domain(domain).role_id(role_id).count()
