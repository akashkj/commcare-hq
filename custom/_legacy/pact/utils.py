from corehq.apps.api.es import ReportCaseESView
from pact.enums import PACT_DOMAIN
from io import BytesIO
from django.test.client import RequestFactory
from corehq.apps.receiverwrapper.views import post
from corehq.apps.es import filters
from corehq.apps.es.cases import CaseES
from corehq.apps.es.forms import FormES


def submit_xform(url_path, domain, submission_xml_string, extra_meta=None):
    """
    RequestFactory submitter
    """
    rf = RequestFactory()
    f = BytesIO(submission_xml_string.encode('utf-8'))
    f.name = 'form.xml'

    req = rf.post(url_path, data={'xml_submission_file': f}) #, content_type='multipart/form-data')
    if extra_meta:
        req.META.update(extra_meta)
    return post(req, domain)


def pact_script_fields():
    """
    This is a hack of the query to allow for the encounter date and pact_ids to show up as first class properties
    """
    return {
        "script_pact_id": {
            "script": """if(_source['form']['note'] != null) { _source['form']['note']['pact_id']['#value']; }
                      else if (_source['form']['pact_id'] != null) { _source['form']['pact_id']['#value']; }
                      else {
                          null;
                      }
                      """
        },
        "script_encounter_date": {
            "script": """if(_source['form']['note'] != null) { _source['form']['note']['encounter_date']['#value']; }
        else if (_source['form']['encounter_date'] != null) { _source['form']['encounter_date']['#value']; }
        else {
            _source['received_on'];
        }
        """
        }
    }


def get_case_id(xform):
    if 'case' in xform['form']:
        if 'case_id' in xform['form']['case']:
            return xform['form']['case']['case_id']
        elif '@case_id' in xform['form']['case']:
            return xform['form']['case']['@case_id']
    return None


def get_patient_display_cache(case_ids):
    """
    For a given set of case_ids, return name and pact_ids
    """
    if len(case_ids) == 0:
        return {}
    case_es = ReportCaseESView(PACT_DOMAIN)
    query = (
        CaseES()
        .remove_default_filters()
        .domain(PACT_DOMAIN)
        .source(["_id", "name"])
        .size(len(case_ids))
    )
    query = query.add_query({"ids": {"values": case_ids}})
    query["script_fields"] = {
        "case_id": {
            "script": "_source._id"
        },
        "pactid": get_report_script_field("pactid"),
        "first_name": get_report_script_field("first_name"),
        "last_name": get_report_script_field("last_name"),
    }
    res = case_es.run_query(query.raw_query)

    from pact.reports.patient import PactPatientInfoReport

    ret = {}
    for entry in res['hits']['hits']:
        case_id = entry['case_id']
        ret[case_id] = entry
        ret[case_id]['url'] = PactPatientInfoReport.get_url(*['pact']) + "?patient_id=%s" % case_id

    return ret


DEFAULT_SIZE = 10


def get_base_form_es_query(start=0, size=DEFAULT_SIZE):
    return (FormES()
        .remove_default_filters()
        .domain(PACT_DOMAIN)
        .filter(filters.term('doc_type', 'XFormInstance'))
        .start(start)
        .size(size))


def get_base_case_es_query(start=0, size=DEFAULT_SIZE):
    return (CaseES()
        .remove_default_filters()
        .domain(PACT_DOMAIN)
        .start(start)
        .size(size))


def get_by_case_id_form_es_query(start, size, case_id):
    base_query = get_base_form_es_query(start, size)
    return (base_query
        .filter(
            filters.nested(
                'form.case',
                filters.OR(
                    filters.term('form.case.@case_id', case_id),
                    filters.term('form.case.case_id', case_id)
                )
            )
        )
    )


def get_report_script_field(field_path, is_known=False):
    """
    Generate a script field string for easier querying.
    field_path: is the path.to.property.name in the _source
    is_known: if true, then query as is, if false, then it's a dynamically mapped item,
    so put on the #value property at the end.
    """
    property_split = field_path.split('.')
    property_path = '_source%s' % ''.join("['%s']" % x for x in property_split)
    if is_known:
        script_string = property_path
    else:
        full_script_path = "%s['#value']" % property_path
        script_string = """if (%(prop_path)s != null) { %(value_path)s; }
        else { null; }""" % {
            'prop_path': property_path,
            'value_path': full_script_path
        }

    ret = {"script": script_string}
    return ret
