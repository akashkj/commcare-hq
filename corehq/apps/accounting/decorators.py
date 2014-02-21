import json
from django.contrib import messages
from django.http import Http404, HttpResponse
from corehq import BillingAccountAdmin, toggles
from django_prbac.decorators import requires_privilege
from django_prbac.exceptions import PermissionDenied
import toggle


def require_billing_admin():
    def decorate(fn):
        """
        Decorator to require the current logged in user to be a billing admin to access the decorated view.
        """
        def wrapped(request, *args, **kwargs):
            if not hasattr(request, 'couch_user') or not hasattr(request, 'domain'):
                raise Http404()
            is_billing_admin = BillingAccountAdmin.get_admin_status_and_account(request.couch_user, request.domain)[0]
            if not (is_billing_admin or request.couch_user.is_superuser):
                raise Http404()
            return fn(request, *args, **kwargs)

        return wrapped

    return decorate


def requires_privilege_alert(slug, **assignment):
    """
    A version of the requires_privilege decorator which inserts an info message into the request
    alerting the user that they will soon loose access to this privilege.
    """
    def decorate(fn):
        def wrapped(request, *args, **kwargs):
            try:
                return requires_privilege(slug, **assignment)(fn)(request, *args, **kwargs)
            except PermissionDenied:
                messaged_slugs = [m.extra_tags for m in messages.get_messages(request)]
                if slug not in messaged_slugs:
                    messages.info(request, "You will soon lose access to this feature", extra_tags=slug)
                return fn(request, *args, **kwargs)
        return wrapped
    return decorate


def requires_privilege_plaintext_response(slug, http_status_code=None, **assignment):
    """
    A version of the requires_privilege decorator which returns an HttpResponse object
    with HTTP Status Code of 412 by default and content_type of tex/plain if the privilege is not found.
    """
    def decorate(fn):
        def wrapped(request, *args, **kwargs):
            if (not hasattr(request, 'user') or
                    not toggle.shortcuts.toggle_enabled(toggles.ACCOUNTING_PREVIEW, request.user.username)):
                return fn(request, *args, **kwargs)
            try:
                return requires_privilege(slug, **assignment)(fn)(request, *args, **kwargs)
            except PermissionDenied:
                return HttpResponse("You have lost access to this feature.",
                                    status=http_status_code or 412, content_type="text/plain")
        return wrapped
    return decorate


def requires_privilege_json_response(slug, http_status_code=None, get_response=None, **assignment):
    """
    A version of the requires privilege decorator which returns an HttpResponse object
    with an HTTP Status Code of 405 by default and content_type application/json if the privilege is not found.
    get_response is an optional parameter where you can specify the format of response given an error
    message and status code. The default response is:
    {
        'code': http_status_Code,
        'message': error_message
    }
    todo accounting for API requests
    """
    http_status_code = http_status_code or 405
    if get_response is None:
        get_response = lambda msg, code: {'code': code, 'message': msg}

    def decorate(fn):
        def wrapped(request, *args, **kwargs):
            if (not hasattr(request, 'user') or
                    not toggle.shortcuts.toggle_enabled(toggles.ACCOUNTING_PREVIEW, request.user.username)):
                return fn(request, *args, **kwargs)
            try:
                return requires_privilege(slug, **assignment)(fn)(request, *args, **kwargs)
            except PermissionDenied:
                error_message = "You have lost access to this feature."
                response = get_response(error_message, http_status_code)
                return HttpResponse(json.dumps(response), content_type="application/json")
        return wrapped
    return decorate


def requires_privilege_for_commcare_user(slug, **assignment):
    """
    A version of the requires_privilege decorator which requires the specified privilege
    only for CommCareUsers.
    """
    def decorate(fn):
        def wrapped(request, *args, **kwargs):
            if hasattr(request, 'couch_user') and request.couch_user.is_web_user():
                return fn(request, *args, **kwargs)
            return requires_privilege_alert(slug, **assignment)(fn)(request, *args, **kwargs)
        return wrapped
    return decorate
