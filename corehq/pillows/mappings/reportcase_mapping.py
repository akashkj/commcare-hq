from corehq.util.elastic import prefix_for_tests
from pillowtop.es_utils import ElasticsearchIndexInfo, REPORT_CASE_HQ_INDEX_NAME


REPORT_CASE_INDEX = prefix_for_tests("report_cases_czei39du507m9mmpqk3y01x72a3ux4p0")

REPORT_CASE_MAPPING = {
    "_meta": {
        "comment": "2013-11-05 dmyung",
        "created": None
    },
    "date_detection": False,
    "date_formats": [
        "yyyy-MM-dd",
        "yyyy-MM-dd'T'HH:mm:ssZZ",
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
        "yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'",
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        "yyyy-MM-dd'T'HH:mm:ssZ",
        "yyyy-MM-dd'T'HH:mm:ssZZ'Z'",
        "yyyy-MM-dd'T'HH:mm:ss.SSSZZ",
        "yyyy-MM-dd'T'HH:mm:ss",
        "yyyy-MM-dd' 'HH:mm:ss",
        "yyyy-MM-dd' 'HH:mm:ss.SSSSSS",
        "mm/dd/yy' 'HH:mm:ss"
    ],
    "dynamic": True,
    "dynamic_templates": [
        {
            "everything_else": {
                "mapping": {
                    "{name}": {
                        "index": "not_analyzed",
                        "type": "string"
                    }
                },
                "match": "*",
                "match_mapping_type": "string"
            }
        }
    ],
    "properties": {
        "actions": {
            "dynamic": True,
            "type": "nested",
            "properties": {
                "action_type": {
                    "type": "string"
                },
                "attachments": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "attachment_from": {
                            "type": "string"
                        },
                        "attachment_name": {
                            "type": "string"
                        },
                        "attachment_properties": {
                            "dynamic": False,
                            "type": "object"
                        },
                        "attachment_size": {
                            "type": "long"
                        },
                        "attachment_src": {
                            "type": "string"
                        },
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "identifier": {
                            "type": "string"
                        },
                        "server_md5": {
                            "type": "string"
                        },
                        "server_mime": {
                            "type": "string"
                        }
                    }
                },
                "date": {
                    "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss",  # noqa: E501
                    "type": "date"
                },
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "indices": {
                    "dynamic": False,
                    "type": "object",
                    "properties": {
                        "doc_type": {
                            "index": "not_analyzed",
                            "type": "string"
                        },
                        "identifier": {
                            "type": "string"
                        },
                        "referenced_id": {
                            "type": "string"
                        },
                        "referenced_type": {
                            "type": "string"
                        }
                    }
                },
                "server_date": {
                    "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss",  # noqa: E501
                    "type": "date"
                },
                "sync_log_id": {
                    "type": "string"
                },
                "updated_known_properties": {
                    "dynamic": False,
                    "type": "object"
                },
                "updated_unknown_properties": {
                    "dynamic": False,
                    "type": "object"
                },
                "user_id": {
                    "type": "string"
                },
                "xform_id": {
                    "type": "string"
                },
                "xform_name": {
                    "type": "string"
                },
                "xform_xmlns": {
                    "type": "string"
                }
            }
        },
        "case_attachments": {
            "dynamic": True,
            "type": "object",
            "properties": {
                "attachment_from": {
                    "type": "string"
                },
                "attachment_name": {
                    "type": "string"
                },
                "attachment_properties": {
                    "dynamic": False,
                    "type": "object"
                },
                "attachment_size": {
                    "type": "long"
                },
                "attachment_src": {
                    "type": "string"
                },
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "identifier": {
                    "type": "string"
                },
                "server_md5": {
                    "type": "string"
                },
                "server_mime": {
                    "type": "string"
                }
            }
        },
        "closed": {
            "type": "boolean"
        },
        "closed_by": {
            "type": "string"
        },
        "closed_on": {
            "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss",  # noqa: E501
            "type": "date"
        },
        "computed_": {
            "enabled": False,
            "type": "object"
        },
        "computed_modified_on_": {
            "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss",  # noqa: E501
            "type": "date"
        },
        "doc_type": {
            "index": "not_analyzed",
            "type": "string"
        },
        "domain": {
            "fields": {
                "domain": {
                    "index": "analyzed",
                    "type": "string"
                },
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                }
            },
            "type": "multi_field"
        },
        "export_tag": {
            "type": "string"
        },
        "external_id": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "external_id": {
                    "index": "analyzed",
                    "type": "string"
                }
            },
            "type": "multi_field"
        },
        "indices": {
            "dynamic": True,
            "type": "object",
            "properties": {
                "doc_type": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "identifier": {
                    "type": "string"
                },
                "referenced_id": {
                    "type": "string"
                },
                "referenced_type": {
                    "type": "string"
                }
            }
        },
        "initial_processing_complete": {
            "type": "boolean"
        },
        "location_id": {
            "type": "string"
        },
        "modified_on": {
            "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss",  # noqa: E501
            "type": "date"
        },
        "name": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "name": {
                    "index": "analyzed",
                    "type": "string"
                }
            },
            "type": "multi_field"
        },
        "opened_by": {
            "type": "string"
        },
        "opened_on": {
            "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss",  # noqa: E501
            "type": "date"
        },
        "owner_id": {
            "type": "string"
        },
        "referrals": {
            "enabled": False,
            "type": "object"
        },
        "server_modified_on": {
            "format": "yyyy-MM-dd||yyyy-MM-dd'T'HH:mm:ssZZ||yyyy-MM-dd'T'HH:mm:ss.SSSSSS||yyyy-MM-dd'T'HH:mm:ss.SSSSSS'Z'||yyyy-MM-dd'T'HH:mm:ss'Z'||yyyy-MM-dd'T'HH:mm:ssZ||yyyy-MM-dd'T'HH:mm:ssZZ'Z'||yyyy-MM-dd'T'HH:mm:ss.SSSZZ||yyyy-MM-dd'T'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss||yyyy-MM-dd' 'HH:mm:ss.SSSSSS||mm/dd/yy' 'HH:mm:ss",  # noqa: E501
            "type": "date"
        },
        "type": {
            "fields": {
                "exact": {
                    "index": "not_analyzed",
                    "type": "string"
                },
                "type": {
                    "index": "analyzed",
                    "type": "string"
                }
            },
            "type": "multi_field"
        },
        "user_id": {
            "type": "string"
        },
        "version": {
            "type": "string"
        },
        "xform_ids": {
            "index": "not_analyzed",
            "type": "string"
        }
    }
}

REPORT_CASE_ES_ALIAS = prefix_for_tests("report_cases")
REPORT_CASE_ES_TYPE = "report_case"

REPORT_CASE_INDEX_INFO = ElasticsearchIndexInfo(
    index=REPORT_CASE_INDEX,
    alias=REPORT_CASE_ES_ALIAS,
    type=REPORT_CASE_ES_TYPE,
    mapping=REPORT_CASE_MAPPING,
    hq_index_name=REPORT_CASE_HQ_INDEX_NAME
)
