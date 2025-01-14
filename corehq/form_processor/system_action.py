import logging

from corehq.form_processor.models import XFormInstanceSQL

log = logging.getLogger(__name__)


def system_action(name):
    """Make a decoractor to register a system action function

    See `do_system_action` docs for expected function signature.

    System actions should be submitted with `system_action.submit(...)`.
    See `submit_system_action` docs for more details.

    :param name: A unique name to be encoded in system action forms and
    used to map them to the corresponding function when the form is
    processed. Once assigned, a system action's name cannot be changed
    without breaking all existing system action forms with that name.
    :returns: A decorator that registers its function as a system action.
    """
    def decorate(func):
        if name in _actions:
            msg = "system action %r already registered (%r)"
            raise ValueError(msg % (name, _actions[name]))
        _actions[name] = func
        return func

    return decorate


def submit_system_action(name, args, args_json, domain):
    """Submit a system action to be recorded as a form

    Alias: `system_action.submit(...)`

    Record a system action (un/archive form, etc.) in the stream of
    submitted forms, which allows it to be reproduced during a
    migration, for example.

    :param name: system action name.
    :param args: list of action arguments, some of which may not be
    JSON-serializable.
    :param args_json: a JSON-serializable object having enough
    information to reconstruct `args` given the action name.
    :param domain: The domain in which to perform the action.
    """
    if name not in _actions:
        raise ValueError("unknown system action: {}".format(name))
    do_system_action(name, args)


system_action.submit = submit_system_action
SYSTEM_ACTION_XMLNS = "http://commcarehq.org/system/action"


def handle_system_action(form, auth_context):
    if auth_context is not SystemActionContext:
        raise UnauthorizedSystemAction(repr(form))
    # put form in archived state so it does not appear in exports
    assert form.xmlns == SYSTEM_ACTION_XMLNS, repr(form)
    if isinstance(form, XFormInstanceSQL):
        form.state = XFormInstanceSQL.ARCHIVED
    else:
        form.doc_type = "XFormArchived"


def do_system_action(name, args):
    """Perform a system action

    This should not normally be called directly except when replaying
    the form stream, during a migration, for example.

    :param name: system action name.
    :param args: system action function arguments.
    """
    _actions[name](*args)


# global system actions registry
_actions = {}


class SystemActionContext(object):

    @staticmethod
    def to_json():
        return {}

    @staticmethod
    def is_valid():
        return True


class UnauthorizedSystemAction(Exception):
    pass
