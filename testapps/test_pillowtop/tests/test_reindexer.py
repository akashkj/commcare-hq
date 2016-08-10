import uuid

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from elasticsearch.exceptions import ConnectionError

from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.es import CaseES, CaseSearchES, DomainES, FormES, UserES, GroupES
from corehq.apps.groups.models import Group
from corehq.apps.groups.tests.test_utils import delete_all_groups
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.elastic import get_es_new
from corehq.form_processor.tests.utils import FormProcessorTestUtils, \
    run_with_all_backends
from corehq.pillows.mappings.case_mapping import CASE_INDEX, CASE_INDEX_INFO
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX
from corehq.pillows.mappings.domain_mapping import DOMAIN_INDEX
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
from corehq.util.elastic import delete_es_index, ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup, create_and_save_a_form, create_and_save_a_case, generate_cases
from pillowtop.checkpoints.manager import DEFAULT_EMPTY_CHECKPOINT_SEQUENCE
from pillowtop.es_utils import initialize_index_and_mapping
from pillowtop.utils import get_pillow_by_name
from testapps.test_pillowtop.utils import real_pillow_settings

DOMAIN = 'reindex-test-domain'


class PillowtopReindexerTest(TestCase):
    domain = DOMAIN

    @classmethod
    def setUpClass(cls):
        super(PillowtopReindexerTest, cls).setUpClass()
        with trap_extra_setup(ConnectionError):
            initialize_index_and_mapping(get_es_new(), CASE_INDEX_INFO)

    @classmethod
    def tearDownClass(cls):
        for index in [CASE_SEARCH_INDEX, USER_INDEX, CASE_INDEX, XFORM_INDEX]:
            ensure_index_deleted(index)
        super(PillowtopReindexerTest, cls).tearDownClass()

    def test_domain_reindexer(self):
        delete_all_domains()
        ensure_index_deleted(DOMAIN_INDEX)
        name = 'reindex-test-domain'
        create_domain(name)
        call_command('ptop_reindexer_v2', index='domain', cleanup=True, noinput=True)
        results = DomainES().run()
        self.assertEqual(1, results.total, results.hits)
        domain_doc = results.hits[0]
        self.assertEqual(name, domain_doc['name'])
        self.assertEqual('Domain', domain_doc['doc_type'])
        delete_es_index(DOMAIN_INDEX)

    @run_with_all_backends
    def test_case_reindexer_v2(self):
        FormProcessorTestUtils.delete_all_cases()
        case = _create_and_save_a_case()

        index_id = 'sql-case' if settings.TESTS_SHOULD_USE_SQL_BACKEND else 'case'
        call_command('ptop_reindexer_v2', index_id, cleanup=True, noinput=True, reset=True)

        self._assert_case_is_in_es(case)

    @run_with_all_backends
    def test_case_search_reindexer(self):
        es = get_es_new()
        FormProcessorTestUtils.delete_all_cases()
        case = _create_and_save_a_case()

        ensure_index_deleted(CASE_SEARCH_INDEX)

        # With case search not enabled, case should not make it to ES
        CaseSearchConfig.objects.all().delete()
        call_command('ptop_reindexer_v2', 'case-search')
        es.indices.refresh(CASE_SEARCH_INDEX)  # as well as refresh the index
        self._assert_es_empty(esquery=CaseSearchES())

        # With case search enabled, it should get indexed
        CaseSearchConfig.objects.create(domain=self.domain, enabled=True)
        self.addCleanup(CaseSearchConfig.objects.all().delete)
        call_command('ptop_reindexer_v2', 'case-search')

        es.indices.refresh(CASE_SEARCH_INDEX)  # as well as refresh the index
        self._assert_case_is_in_es(case, esquery=CaseSearchES())

    @run_with_all_backends
    def test_xform_reindexer_v2(self):
        FormProcessorTestUtils.delete_all_xforms()
        form = create_and_save_a_form(DOMAIN)

        index_id = 'sql-form' if settings.TESTS_SHOULD_USE_SQL_BACKEND else 'form'
        call_command('ptop_reindexer_v2', index_id, cleanup=True, noinput=True, reset=True)

        self._assert_form_is_in_es(form)

    def _assert_es_empty(self, esquery=CaseES()):
        results = esquery.run()
        self.assertEqual(0, results.total)

    def _assert_case_is_in_es(self, case, esquery=CaseES()):
        results = esquery.run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]
        self.assertEqual(case.case_id, case_doc['_id'])
        self.assertEqual(self.domain, case_doc['domain'])
        self.assertEqual(case.name, case_doc['name'])
        self.assertEqual('CommCareCase', case_doc['doc_type'])

    def _assert_form_is_in_es(self, form):
        results = FormES().run()
        self.assertEqual(1, results.total)
        form_doc = results.hits[0]
        self.assertEqual(self.domain, form_doc['domain'])
        self.assertEqual(form.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])

    def _assert_index_empty(self, esquery=CaseES()):
        results = esquery.run()
        self.assertEqual(0, results.total)


class CheckpointCreationTest(TestCase):
    # this class is only here so you can run these explicitly
    pass


@generate_cases([
    ('app', 'ApplicationToElasticsearchPillow'),
    ('case', 'CaseToElasticsearchPillow'),
    ('form', 'XFormToElasticsearchPillow'),
    ('domain', 'KafkaDomainPillow'),
    ('user', 'UserPillow'),
    ('group', 'GroupPillow'),
    ('ledger-v1', 'LedgerToElasticsearchPillow'),
    ('sms', 'SqlSMSPillow'),
    ('report-case', 'ReportCaseToElasticsearchPillow'),
    ('report-xform', 'ReportXFormToElasticsearchPillow'),
], CheckpointCreationTest)
def test_checkpoint_creation(self, reindex_id, pillow_name):
    with real_pillow_settings():
        pillow = get_pillow_by_name(pillow_name)
        random_seq = uuid.uuid4().hex
        pillow.checkpoint.update_to(random_seq)
        self.assertEqual(random_seq, pillow.checkpoint.get_current_sequence_id())
        call_command('ptop_reindexer_v2', reindex_id, cleanup=True, noinput=True)
        pillow = get_pillow_by_name(pillow_name)
        self.assertNotEqual(random_seq, pillow.checkpoint.get_current_sequence_id())
        self.assertEqual(
            str(pillow.get_change_feed().get_checkpoint_value()),
            pillow.checkpoint.get_current_sequence_id(),
        )


@generate_cases([
    ('sql-case', 'CaseToElasticsearchPillow'),
    ('sql-form', 'XFormToElasticsearchPillow'),
    ('ledger-v2', 'LedgerToElasticsearchPillow'),
    ('groups-to-user', 'UserPillow'),
], CheckpointCreationTest)
def test_no_checkpoint_creation(self, reindex_id, pillow_name):
    # these pillows should not touch checkpoints since they are run with other
    # reindexers
    with real_pillow_settings():
        pillow = get_pillow_by_name(pillow_name)
        random_seq = uuid.uuid4().hex
        pillow.checkpoint.update_to(random_seq)
        self.assertEqual(random_seq, pillow.checkpoint.get_current_sequence_id())
        call_command('ptop_reindexer_v2', reindex_id, cleanup=True, noinput=True)
        pillow = get_pillow_by_name(pillow_name)
        self.assertEqual(
            random_seq,
            pillow.checkpoint.get_current_sequence_id(),
        )

class UserReindexerTest(TestCase):
    dependent_apps = [
        'auditcare', 'django_digest', 'pillowtop',
        'corehq.apps.domain', 'corehq.apps.users', 'corehq.apps.tzmigration',
    ]

    def setUp(self):
        super(UserReindexerTest, self).setUp()
        delete_all_users()

    @classmethod
    def setUpClass(cls):
        super(UserReindexerTest, cls).setUpClass()
        create_domain(DOMAIN)
        ensure_index_deleted(USER_INDEX)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(USER_INDEX)
        super(UserReindexerTest, cls).tearDownClass()

    def test_user_reindexer_v2(self):
        username = 'reindex-test-username-v2'
        CommCareUser.create(DOMAIN, username, 'secret')
        call_command('ptop_reindexer_v2', **{'index': 'user', 'cleanup': True, 'noinput': True})
        self._assert_user_in_es(username)

    def test_web_user_reindexer_v2(self):
        username = 'test-v2@example.com'
        WebUser.create(DOMAIN, username, 'secret')
        call_command('ptop_reindexer_v2', **{'index': 'user', 'cleanup': True, 'noinput': True})
        self._assert_user_in_es(username, is_webuser=True)

    def _assert_user_in_es(self, username, is_webuser=False):
        results = UserES().run()
        self.assertEqual(1, results.total)
        user_doc = results.hits[0]
        self.assertEqual(username, user_doc['username'])
        if not is_webuser:
            self.assertEqual(DOMAIN, user_doc['domain'])
            self.assertEqual('CommCareUser', user_doc['doc_type'])
        else:
            self.assertEqual('WebUser', user_doc['doc_type'])


class GroupReindexerTest(TestCase):
    dependent_apps = [
        'pillowtop',
        'corehq.couchapps',
        'corehq.apps.groups',
    ]

    def setUp(self):
        super(GroupReindexerTest, self).setUp()
        delete_all_groups()

    @classmethod
    def setUpClass(cls):
        super(GroupReindexerTest, cls).setUpClass()
        ensure_index_deleted(GROUP_INDEX_INFO.index)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(GROUP_INDEX_INFO.index)
        super(GroupReindexerTest, cls).tearDownClass()

    def test_group_reindexer(self):
        group = Group(domain=DOMAIN, name='g1')
        group.save()
        call_command('ptop_reindexer_v2', **{'index': 'group', 'cleanup': True, 'noinput': True})
        self._assert_group_in_es(group)

    def _assert_group_in_es(self, group):
        results = GroupES().run()
        self.assertEqual(1, results.total)
        es_group = results.hits[0]
        self.assertEqual(group._id, es_group['_id'])
        self.assertEqual(group.name, es_group['name'])
        self.assertEqual(group.users, es_group['users'])
        self.assertEqual('Group', es_group['doc_type'])


def _create_and_save_a_case():
    case_name = 'reindexer-test-case-{}'.format(uuid.uuid4().hex)
    case_id = uuid.uuid4().hex
    return create_and_save_a_case(DOMAIN, case_id, case_name)
