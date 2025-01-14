from unittest.mock import MagicMock
from uuid import uuid4

from django.test import SimpleTestCase, TestCase

from nose.tools import assert_equal

from casexml.apps.case.mock import CaseFactory, CaseIndex, CaseStructure

from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import Attachment, CommCareCaseSQL

DOMAIN = 'test-domain'


class AttachmentHasSizeTests(SimpleTestCase):
    def test_handles_no_size_property(self):
        raw_content = MagicMock(spec_set=[''])
        attachment = self.create_attachment_with_content(raw_content)
        self.assertFalse(attachment.has_size())

    def test_handles_None(self):
        raw_content = MagicMock(size=None, spec_set=['size'])
        attachment = self.create_attachment_with_content(raw_content)
        self.assertFalse(attachment.has_size())

    def test_handles_valid_size(self):
        raw_content = MagicMock(size=1024, spec_set=['size'])
        attachment = self.create_attachment_with_content(raw_content)
        self.assertTrue(attachment.has_size())

    @staticmethod
    def create_attachment_with_content(content):
        return Attachment(name='test_attachment', raw_content=content, content_type='text')


class TestIndices(TestCase):
    """
    Verify that when two indices are created with the same identifier,
    CommCareCaseSQL.indices returns only the last one created.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.factory = CaseFactory(domain=DOMAIN)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

    def setUp(self):
        johnny_id = str(uuid4())
        nathaniel_id = str(uuid4())
        elizabeth_id = str(uuid4())
        (self.johnny_case,
         self.nathaniel_case,
         self.elizabeth_case) = self.factory.create_or_update_case(
            CaseStructure(
                case_id=johnny_id,
                attrs={
                    'create': True,
                    'case_type': 'child',
                    'case_name': 'Johnny APPLESEED',
                    'owner_id': 'b0b',
                    'external_id': 'johnny12345',
                    'update': {
                        'first_name': 'Johnny',
                        'last_name': 'Appleseed',
                        'date_of_birth': '2021-08-27',
                        'dhis2_org_unit_id': 'abcdef12345',
                    },
                },
                indices=[
                    CaseIndex(
                        CaseStructure(
                            case_id=nathaniel_id,
                            attrs={
                                'create': True,
                                'case_type': 'parent',
                                'case_name': 'Nathaniel CHAPMAN',
                                'owner_id': 'b0b',
                                'external_id': 'nathaniel12',
                                'update': {
                                    'first_name': 'Nathaniel',
                                    'last_name': 'Chapman',
                                    'dhis2_org_unit_id': 'abcdef12345',
                                },
                            },
                        ),
                        relationship='child',
                        related_type='parent',
                        identifier='parent',
                    ),
                    CaseIndex(
                        CaseStructure(
                            case_id=elizabeth_id,
                            attrs={
                                'create': True,
                                'case_type': 'parent',
                                'case_name': 'Elizabeth SIMONDS',
                                'owner_id': 'b0b',
                                'external_id': 'elizabeth12',
                                'update': {
                                    'first_name': 'Elizabeth',
                                    'last_name': 'Simonds',
                                    'dhis2_org_unit_id': 'abcdef12345',
                                },
                            },
                        ),
                        relationship='child',
                        related_type='parent',
                        identifier='parent',
                    )
                ],
            )
        )

    def test_case_indices(self):
        indices = self.johnny_case.indices
        self.assertEqual(len(indices), 1)

        case_accessor = CaseAccessors(DOMAIN)
        case = case_accessor.get_case(indices[0].referenced_id)
        self.assertTrue(are_cases_equal(case, self.elizabeth_case))


def are_cases_equal(a, b):  # or at least equal enough for our test
    attrs = ('domain', 'case_id', 'type', 'name', 'owner_id')
    return all(getattr(a, attr) == getattr(b, attr) for attr in attrs)


def test_case_to_json():
    case_id = str(uuid4())
    case = CommCareCaseSQL(
        case_id=case_id,
        domain=DOMAIN,
        type='case',
        name='Justin Case',
        case_json={
            'given_name': 'Justin',
            'family_name': 'Case',
            'actions': 'eating sleeping typing',
            'indices': 'Dow_Jones_Industrial_Average S&P_500',
        },
    )
    case_dict = case.to_json()
    assert_equal(case_dict, {
        '_id': case_id,
        'actions': [],  # Not replaced by case_json
        'backend_id': 'sql',
        'case_attachments': {},
        'case_id': case_id,
        'case_json': {
            'actions': 'eating sleeping typing',
            'family_name': 'Case',
            'given_name': 'Justin',
            'indices': 'Dow_Jones_Industrial_Average S&P_500',
        },
        'closed': False,
        'closed_by': None,
        'closed_on': None,
        'deleted': False,
        'doc_type': 'CommCareCase',
        'domain': DOMAIN,
        'external_id': None,
        'family_name': 'Case',
        'given_name': 'Justin',
        'indices': [],  # Not replaced by case_json
        'location_id': None,
        'modified_by': '',
        'modified_on': None,
        'name': 'Justin Case',
        'opened_by': None,
        'opened_on': None,
        'owner_id': '',
        'server_modified_on': None,
        'type': 'case',
        'user_id': '',
        'xform_ids': [],
    })
