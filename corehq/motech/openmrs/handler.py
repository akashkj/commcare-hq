from __future__ import absolute_import
from __future__ import unicode_literals

from datetime import timedelta

from corehq.motech.const import DIRECTION_EXPORT
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.openmrs.const import PERSON_UUID_IDENTIFIER_TYPE_ID
from corehq.motech.openmrs.repeater_helpers import (
    CreatePatientIdentifierTask,
    CreatePersonAttributeTask,
    CreateVisitTask,
    DeletePersonAttributeTask,
    UpdatePatientIdentifierTask,
    UpdatePersonAttributeTask,
    get_ancestor_location_openmrs_uuid,
    get_unknown_location_uuid,
)
from corehq.motech.openmrs.serializers import to_omrs_datetime
from corehq.motech.openmrs.workflow import WorkflowTask
from dimagi.utils.parsing import string_to_utc_datetime


class SyncPersonAttributesTask(WorkflowTask):

    def __init__(self, requests, info, openmrs_config, person_uuid, attributes):
        self.requests = requests
        self.info = info
        self.openmrs_config = openmrs_config
        self.person_uuid = person_uuid
        self.attributes = attributes

    def run(self):
        """
        Returns WorkflowTasks for creating and updating OpenMRS person attributes.
        """
        subtasks = []
        existing_person_attributes = {
            attribute['attributeType']['uuid']: (attribute['uuid'], attribute['value'])
            for attribute in self.attributes
        }
        for person_attribute_type, value_source in self.openmrs_config.case_config.person_attributes.items():
            if not value_source.check_direction(DIRECTION_EXPORT):
                continue
            value = value_source.get_value(self.info)
            if person_attribute_type in existing_person_attributes:
                attribute_uuid, existing_value = existing_person_attributes[person_attribute_type]
                if value != existing_value:
                    if value in ("", None):
                        subtasks.append(
                            DeletePersonAttributeTask(
                                self.requests, self.person_uuid, attribute_uuid, person_attribute_type,
                                existing_value
                            )
                        )
                    else:
                        subtasks.append(
                            UpdatePersonAttributeTask(
                                self.requests, self.person_uuid, attribute_uuid, person_attribute_type, value,
                                existing_value
                            )
                        )
            else:
                subtasks.append(
                    CreatePersonAttributeTask(self.requests, self.person_uuid, person_attribute_type, value)
                )
        return subtasks


class SyncPatientIdentifiersTask(WorkflowTask):

    def __init__(self, requests, info, openmrs_config, patient):
        self.requests = requests
        self.info = info
        self.openmrs_config = openmrs_config
        self.patient = patient

    def run(self):
        """
        Returns WorkflowTasks for creating and updating OpenMRS patient identifiers.
        """
        subtasks = []
        existing_patient_identifiers = {
            identifier['identifierType']['uuid']: (identifier['uuid'], identifier['identifier'])
            for identifier in self.patient['identifiers']
        }
        for patient_identifier_type, value_source in self.openmrs_config.case_config.patient_identifiers.items():
            if not value_source.check_direction(DIRECTION_EXPORT):
                continue
            if patient_identifier_type == PERSON_UUID_IDENTIFIER_TYPE_ID:
                # Don't try to sync the OpenMRS person UUID; It's not a
                # user-defined identifier and it can't be changed.
                continue
            identifier = value_source.get_value(self.info)
            # If the patient is new, and its case property that
            # corresponds to the identifier is blank, then the
            # patient's identifier will have been generated by
            # repeater_helpers.generate_identifier(). The case will have
            # been updated by repeater_helpers.save_match_ids() but
            # self.info will not contain the newly-generated identifier.
            # `identifier` will be None. Don't try to update the
            # patient's identifier to None; it's already set correctly.
            if not identifier:
                continue
            if patient_identifier_type in existing_patient_identifiers:
                identifier_uuid, existing_identifier = existing_patient_identifiers[patient_identifier_type]
                if identifier != existing_identifier:
                    subtasks.append(
                        UpdatePatientIdentifierTask(
                            self.requests, self.patient['uuid'], identifier_uuid, patient_identifier_type,
                            identifier, existing_identifier
                        )
                    )
            else:
                subtasks.append(
                    CreatePatientIdentifierTask(
                        self.requests, self.patient['uuid'], patient_identifier_type, identifier
                    )
                )
        return subtasks


class CreateVisitsEncountersObsTask(WorkflowTask):

    def __init__(self, requests, domain, info, form_json, form_question_values, openmrs_config, person_uuid):
        self.requests = requests
        self.domain = domain
        self.info = info
        self.form_json = form_json
        self.form_question_values = form_question_values
        self.openmrs_config = openmrs_config
        self.person_uuid = person_uuid

    def _get_start_stop_datetime(self, form_config):
        """
        Returns a start datetime for the Visit and the Encounter, and a
        stop_datetime for the Visit
        """
        if form_config.openmrs_start_datetime:
            cc_start_datetime_str = form_config.openmrs_start_datetime._get_commcare_value(self.info)
            if cc_start_datetime_str is None:
                raise ConfigurationError(
                    'A form config for form XMLNS "{}" uses "openmrs_start_datetime" to get the start of '
                    'the visit but no value was found in the form.'.format(form_config.xmlns)
                )
            try:
                cc_start_datetime = string_to_utc_datetime(cc_start_datetime_str)
            except ValueError:
                raise ConfigurationError(
                    'A form config for form XMLNS "{}" uses "openmrs_start_datetime" to get the start of '
                    'the visit but an invalid value was found in the form.'.format(form_config.xmlns)
                )
            cc_stop_datetime = cc_start_datetime + timedelta(days=1) - timedelta(seconds=1)
            # We need to use openmrs_start_datetime.serialize()
            # for both values because they could be either
            # OpenMRS datetimes or OpenMRS dates, and their data
            # types must match.
            start_datetime = form_config.openmrs_start_datetime.serialize(cc_start_datetime)
            stop_datetime = form_config.openmrs_start_datetime.serialize(cc_stop_datetime)
        else:
            cc_start_datetime = string_to_utc_datetime(self.form_json['form']['meta']['timeEnd'])
            cc_stop_datetime = cc_start_datetime + timedelta(days=1) - timedelta(seconds=1)
            start_datetime = to_omrs_datetime(cc_start_datetime)
            stop_datetime = to_omrs_datetime(cc_stop_datetime)
        return start_datetime, stop_datetime

    def run(self):
        """
        Returns WorkflowTasks for creating visits, encounters and observations
        """
        subtasks = []
        provider_uuid = getattr(self.openmrs_config, 'openmrs_provider', None)
        location_uuid = (
            get_ancestor_location_openmrs_uuid(self.domain, self.info.case_id) or
            get_unknown_location_uuid(self.requests)  # If we don't set
            # a location, OpenMRS sets it to NULL. That's OK for
            # OpenMRS, but it breaks Bahmni. Bahmni has an "Unknown
            # Location". Use that, if it exists.
        )
        self.info.form_question_values.update(self.form_question_values)
        for form_config in self.openmrs_config.form_configs:
            if form_config.xmlns == self.form_json['form']['@xmlns']:
                start_datetime, stop_datetime = self._get_start_stop_datetime(form_config)
                subtasks.append(
                    CreateVisitTask(
                        self.requests,
                        person_uuid=self.person_uuid,
                        provider_uuid=provider_uuid,
                        start_datetime=start_datetime,
                        stop_datetime=stop_datetime,
                        values_for_concept={obs.concept: [obs.value.get_value(self.info)]
                                            for obs in form_config.openmrs_observations
                                            if obs.value.get_value(self.info)},
                        encounter_type=form_config.openmrs_encounter_type,
                        openmrs_form=form_config.openmrs_form,
                        visit_type=form_config.openmrs_visit_type,
                        location_uuid=location_uuid,
                    )
                )
        return subtasks
