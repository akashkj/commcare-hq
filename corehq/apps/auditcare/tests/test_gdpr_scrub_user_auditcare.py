from django.core import management

from couchdbkit.ext.django.loading import get_db

from ..models import AccessAudit, NavigationEventAudit
from .testutils import AuditcareTest, save_couch_doc, delete_couch_docs

USERNAME = "gdpr_user1"


class TestGDPRScrubUserAuditcare(AuditcareTest):

    def setUp(self):
        NavigationEventAudit(user=USERNAME, path="/fake/path/0").save()
        NavigationEventAudit(user=USERNAME, path="/fake/path/1").save()
        NavigationEventAudit(user=USERNAME, path="/fake/path/2").save()
        AccessAudit(user=USERNAME, path="/fake/login").save()
        AccessAudit(user=USERNAME, path="/fake/logout").save()
        self.couch_ids = [
            save_couch_doc("NavigationEventAudit", USERNAME, path="/fake/path/3"),
            save_couch_doc("AccessAudit", USERNAME, ip_address="123.45.67.89"),
        ]

    def tearDown(self):
        delete_couch_docs(self.couch_ids)

    def test_update_username_no_returned_docs(self):
        management.call_command("gdpr_scrub_user_auditcare", "nonexistent_user")
        self.assertEqual(count_events("Redacted User (GDPR)"), 0)
        self.assertEqual(count_events(USERNAME), 7)

    def test_update_username_returned_docs(self):
        management.call_command("gdpr_scrub_user_auditcare", USERNAME)
        self.assertEqual(count_events("Redacted User (GDPR)"), 7)
        self.assertEqual(count_events(USERNAME), 0)


def count_events(username):
    return sum([
        AccessAudit.objects.filter(user=username).count(),
        NavigationEventAudit.objects.filter(user=username).count(),
        couch_count(username),
    ])


def couch_count(username):
    return get_db("auditcare").view(
        "auditcare/urlpath_by_user_date",
        startkey=[username],
        endkey=[username, {}],
        reduce=False,
        include_docs=False,
    ).count()
