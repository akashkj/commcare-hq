import itertools

from django.utils.translation import ugettext as _

from dimagi.ext import jsonobject

from corehq.apps.app_manager.app_schemas.case_properties import (
    get_all_case_properties_for_case_type,
)
from corehq.apps.case_importer.util import RESERVED_FIELDS
from corehq.apps.data_dictionary.util import get_values_hints_dict, get_deprecated_fields
from corehq.toggles import BULK_UPLOAD_DATE_OPENED


def _combine_field_specs(field_specs, exclude_fields):
    """
    take a list of FieldSpec objects and return a sorted list where field is unique
    and fields in exclude_fields are removed, and where the first mention of a
    field in field_specs will win out over any repeats.

    """

    combined_field_specs = {}

    for field_spec in field_specs:
        field = field_spec.field
        if field not in exclude_fields and field not in combined_field_specs:
            combined_field_specs[field] = field_spec

    return sorted(list(combined_field_specs.values()), key=lambda field_spec: field_spec.field)


def get_suggested_case_fields(domain, case_type, exclude=None):
    exclude_fields = set(RESERVED_FIELDS) | set(exclude or [])
    hints_dict = get_values_hints_dict(domain, case_type)
    deprecated_fields = get_deprecated_fields(domain, case_type)

    special_field_specs = (field_spec for field_spec in get_special_fields(domain))

    dynamic_field_specs = (
        FieldSpec(field=field, show_in_menu=True, values_hints=hints_dict[field],
                  deprecated=field in deprecated_fields)
        for field in get_all_case_properties_for_case_type(domain, case_type, exclude_deprecated_properties=False))

    return _combine_field_specs(
        itertools.chain(special_field_specs, dynamic_field_specs),
        exclude_fields=exclude_fields
    )


class FieldSpec(jsonobject.StrictJsonObject):
    field = jsonobject.StringProperty()
    description = jsonobject.StringProperty()
    show_in_menu = jsonobject.BooleanProperty(default=False)
    discoverable = jsonobject.BooleanProperty(default=True)
    values_hints = jsonobject.ListProperty()
    deprecated = jsonobject.BooleanProperty(default=False)


def get_special_fields(domain=None):
    special_fields = [
        FieldSpec(
            field='name',
            description=_("This field will be used to set the case's name."),
            show_in_menu=True),
        FieldSpec(
            field='owner_name',
            description=_("This field will assign the case to a new owner given by "
                          "Username, Group name, or Organization name."),
        ),
        FieldSpec(
            field='owner_id',
            description=_("This field will assign the case to a new owner given by "
                          "User ID, Group ID, or Organization ID.")),
        FieldSpec(
            field='external_id',
            description=_("This field will set the case's external_id")),
        FieldSpec(
            field='parent_external_id',
            description=_("This field will assign the case a new parent given by "
                          "the parent case's external_id. "
                          "You must use along with parent_type.")),
        FieldSpec(
            field='parent_id',
            description=_("This field will assign the case a new parent given by "
                          "the parent's Case ID. "
                          "You must use along with parent_type.")),
        FieldSpec(
            field='parent_type',
            description=_("Use to specify the parent's case type. "
                          "Usually used with parent_id or parent_external_id")),
        FieldSpec(
            field='parent_relationship_type',
            description=_("Whether the relationship with the parent is 'child' or "
                          "'extension'. Default value is 'child'"
                          "Values other than 'child' or 'extension' are invalid. "
                          "Used with parent_id or parent_external_id columns")),
        FieldSpec(
            field='parent_identifier',
            description=_("The index identifier when creating child/extension cases "
                          "Used with parent_id or parent_external_id columns")),
        FieldSpec(
            field='close',
            description=_("This field will be used to close cases. "
                          "Any case with 'yes' in this column will be closed.")),
    ]
    if domain and BULK_UPLOAD_DATE_OPENED.enabled(domain):
        special_fields.append(
            FieldSpec(
                field='date_opened',
                description=_(
                    "The date opened property for this case will be changed. "
                    "Please do not use unless you know what you are doing"
                )
            )
        )
    return special_fields
