from corehq.pillows.core import DATE_FORMATS_ARR, DATE_FORMATS_STRING
from corehq.pillows.mappings import NULL_VALUE
from corehq.util.elastic import es_index
from pillowtop.es_utils import ElasticsearchIndexInfo

CASE_INDEX = es_index("hqcases_2016-03-04")
CASE_ES_TYPE = 'case'

CASE_MAPPING = {
    'date_detection': False,
    'date_formats': DATE_FORMATS_ARR,
    'dynamic': False,
    '_meta': {
        'comment': '',
        'created': '2013-09-19 @dmyung'
    },
    'properties': {
        'actions': {'dynamic': False,
                    'properties': {
                        'action_type': {'type': 'string'},
                        'date': {'format': DATE_FORMATS_STRING,
                                 'type': 'date'},
                        'doc_type': {'index': 'not_analyzed',
                                     'type': 'string'},
                        'indices': {'dynamic': False,
                                    'properties': {
                                        'doc_type': {'index': 'not_analyzed',
                                                     'type': 'string'},
                                        'identifier': {'type': 'string'},
                                        'referenced_id': {'type': 'string'},
                                        'referenced_type': {'type': 'string'}
                                    },
                                    'type': 'object'},
                        'server_date': {'format': DATE_FORMATS_STRING,
                                        'type': 'date'},
                        'sync_log_id': {'type': 'string'},
                        'user_id': {'type': 'string'},
                        'xform_id': {'type': 'string'},
                        'xform_name': {'type': 'string'},
                        'xform_xmlns': {'type': 'string'}
                    },
                    'type': 'nested'},
        'closed': {'type': 'boolean'},
        # todo; check with team
        'closed_by': {"type": "string", "index": "not_analyzed"},
        'closed_on': {'format': DATE_FORMATS_STRING,
                      'type': 'date'},
        'computed_': {'enabled': False,
                      'type': 'object'},
        'computed_modified_on_': {'format': DATE_FORMATS_STRING,
                                  'type': 'date'},
        'doc_type': {'index': 'not_analyzed',
                     'type': 'string'},
        'inserted_at': {"type": "date", "format": DATE_FORMATS_STRING},
        'domain': {'fields': {'domain': {'index': 'analyzed',
                                         'type': 'string'},
                              'exact': {'index': 'not_analyzed',
                                        'type': 'string'}},
                   'type': 'multi_field'},
        'export_tag': {'type': 'string'},
        'external_id': {'fields': {'exact': {'index': 'not_analyzed',
                                             'type': 'string'},
                                   'external_id': {'index': 'analyzed',
                                                   'type': 'string'}},
                        'type': 'multi_field'},
        'indices': {'dynamic': False,
                    'properties': {'doc_type': {'index': 'not_analyzed',
                                                'type': 'string'},
                                   'identifier': {'type': 'string'},
                                   'referenced_id': {'type': 'string'},
                                   'referenced_type': {'type': 'string'}},
                    'type': 'object'},
        'initial_processing_complete': {'type': 'boolean'},
        'location_id': {'type': 'string'},
        'modified_on': {'format': DATE_FORMATS_STRING,
                        'type': 'date'},
        'name': {'fields': {'exact': {'index': 'not_analyzed',
                                      'type': 'string'},
                            'name': {'index': 'analyzed',
                                     'type': 'string'}},
                 'type': 'multi_field'},
        # todo; check with team
        'opened_by': {"type": "string", "index": "not_analyzed"},
        'opened_on': {'format': DATE_FORMATS_STRING,
                      'type': 'date'},
        # Todo; check with team whether okay to update this without triggering reindex for other envs
        "owner_id": {"type": "string", "index": "not_analyzed"},
        'owner_type': {'type': 'string', "index": "not_analyzed", "null_value": NULL_VALUE},
        'referrals': {'enabled': False, 'type': 'object'},
        'server_modified_on': {'format': DATE_FORMATS_STRING,
                               'type': 'date'},
        'type': {'fields': {'exact': {'index': 'not_analyzed',
                                      'type': 'string'},
                            'type': {'index': 'analyzed',
                                     'type': 'string'}},
                 'type': 'multi_field'},
        'user_id': {'type': 'string'},
        'version': {'type': 'string'},
        'xform_ids': {'index': 'not_analyzed',
                      'type': 'string'},
        'contact_phone_number': {'index': 'not_analyzed',
                                 'type': 'string'},
        'backend_id': {'type': 'string', 'index': 'not_analyzed'},
    }
}

CASE_ES_ALIAS = "hqcases"

CASE_INDEX_INFO = ElasticsearchIndexInfo(
    index=CASE_INDEX,
    alias=CASE_ES_ALIAS,
    type=CASE_ES_TYPE,
    mapping=CASE_MAPPING
)
