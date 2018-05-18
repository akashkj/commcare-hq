from __future__ import absolute_import
from __future__ import unicode_literals
from django.db import models
from django.utils.translation import ugettext_lazy as _
from jsonfield import JSONField
from memoized import memoized

from corehq.apps.aggregate_ucrs.column_specs import PRIMARY_COLUMN_TYPE_CHOICES, PrimaryColumnAdapter
from corehq.apps.userreports.datatypes import DATA_TYPE_STRING, DATA_TYPE_DATE
from corehq.apps.userreports.indicators import Column
from corehq.apps.userreports.models import get_datasource_config
from corehq.sql_db.connections import UCR_ENGINE_ID


MAX_COLUMN_NAME_LENGTH = MAX_TABLE_NAME_LENGTH = 63


class AggregateTableDefinition(models.Model):
    """
    An aggregate table definition associated with multiple UCR data sources.
    Used to "join" data across multiple UCR tables.
    """
    AGGREGATION_UNIT_CHOICE_MONTH = 'month'
    AGGREGATION_UNIT_CHOICES = (
        (AGGREGATION_UNIT_CHOICE_MONTH, _('Month')),
    )
    domain = models.CharField(max_length=100)
    engine_id = models.CharField(default=UCR_ENGINE_ID, max_length=100)
    table_id = models.CharField(max_length=MAX_TABLE_NAME_LENGTH)
    display_name = models.CharField(max_length=100, null=True, blank=True)
    date_created = models.DateTimeField(auto_now_add=True)
    date_modified = models.DateTimeField(auto_now=True)

    # primary data source reference
    primary_data_source_id = models.UUIDField()  # id of DataSourceConfig
    primary_data_source_key = models.CharField(default='doc_id', max_length=MAX_COLUMN_NAME_LENGTH)

    # aggregation config
    aggregation_unit = models.CharField(max_length=10, choices=AGGREGATION_UNIT_CHOICES,
                                        default=AGGREGATION_UNIT_CHOICE_MONTH)
    aggregation_start_column = models.CharField(default='opened_date', max_length=MAX_COLUMN_NAME_LENGTH)
    aggregation_end_column = models.CharField(default='closed_date', max_length=MAX_COLUMN_NAME_LENGTH)

    @property
    @memoized
    def data_source(self):
        return get_datasource_config(self.primary_data_source_id.hex, self.domain)[0]

    def get_columns(self):
        """
        :return:
        """
        yield self._get_id_column_spec()
        yield self._get_aggregation_column_spec()
        for primary_column in self.primary_columns.all():
            yield primary_column.to_column_spec()
        for secondary_table in self.secondary_tables.all():
            for secondary_column in secondary_table.columns.all():
                # todo: secondary column support
                # yield secondary_column.to_column_spec()
                pass

    def _get_id_column_spec(self):
        return Column('doc_id', datatype=DATA_TYPE_STRING, is_nullable=False,
                      is_primary_key=True, create_index=True)

    def _get_aggregation_column_spec(self):
        if self.aggregation_unit == self.AGGREGATION_UNIT_CHOICE_MONTH:
            return Column('month', datatype=DATA_TYPE_DATE, is_nullable=False,
                          is_primary_key=True, create_index=True)
        else:
            raise Exception(
                'Aggregation units apart from {} are not supported'.format(
                    ', '.join(u[0] for u in self.AGGREGATION_UNIT_CHOICES)
                )
            )


class PrimaryColumn(models.Model):
    """
    A reference to a primary column in an aggregate table
    """
    table_definition = models.ForeignKey(AggregateTableDefinition, on_delete=models.CASCADE,
                                         related_name='primary_columns')
    column_id = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)
    column_type = models.CharField(max_length=20, choices=PRIMARY_COLUMN_TYPE_CHOICES)
    config_params = JSONField()

    def to_column_spec(self):
        return PrimaryColumnAdapter.from_db_column(self).to_ucr_column_spec()


class SecondaryTableDefinition(models.Model):
    """
    A reference to a secondary table in an aggregate table
    """
    table_definition = models.ForeignKey(AggregateTableDefinition, on_delete=models.CASCADE,
                                         related_name='secondary_tables')
    data_source = models.UUIDField()
    data_source_key = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)
    aggregation_column = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)


class SecondaryColumn(models.Model):
    """
    An aggregate column in an aggregate data source.
    """
    AGGREGATE_COLUMN_TYPE_SUM = 'sum'
    AGGREGATE_COLUMN_TYPE_CHOICES = (
        (AGGREGATE_COLUMN_TYPE_SUM, _('Sum')),
    )
    table_definition = models.ForeignKey(SecondaryTableDefinition, on_delete=models.CASCADE,
                                         related_name='columns')
    column_id = models.CharField(max_length=MAX_COLUMN_NAME_LENGTH)
    aggregation_type = models.CharField(max_length=10, choices=AGGREGATE_COLUMN_TYPE_CHOICES)
    config_params = JSONField()

    def to_column_spec(self):
        # todo
        # return SecondaryColumnAdapter.from_db_column(self).to_ucr_column_spec()
        pass
