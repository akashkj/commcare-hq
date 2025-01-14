from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_lazy

from crispy_forms import layout as crispy

from dimagi.utils.django.fields import TrimmedCharField

from corehq.apps.sms.forms import BackendForm

from ..http.form_handling import form_clean_url


class AirtelTCLBackendForm(BackendForm):
    host_and_port = TrimmedCharField(
        label=ugettext_lazy("Host:Port"),
        required=True,
    )
    user_name = TrimmedCharField(
        label=ugettext_lazy("Username"),
        required=True,
    )
    password = TrimmedCharField(
        label=ugettext_lazy("Password"),
        required=True,
    )
    sender_id = TrimmedCharField(
        label=ugettext_lazy("Sender ID"),
        required=True,
    )
    circle_name = TrimmedCharField(
        label=ugettext_lazy("Circle Name"),
        required=True,
    )
    campaign_name = TrimmedCharField(
        label=ugettext_lazy("Campaign Name"),
        required=True,
    )

    @property
    def gateway_specific_fields(self):
        return crispy.Fieldset(
            _("Airtel (through TCL) Settings"),
            'host_and_port',
            'user_name',
            'password',
            'sender_id',
            'circle_name',
            'campaign_name',
        )

    def clean_host_and_port(self):
        host_and_port = self.cleaned_data.get('host_and_port')
        return form_clean_url(host_and_port)
