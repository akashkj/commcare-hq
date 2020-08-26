from django.conf.urls import url

from corehq.motech.dhis2.views import DataSetMapListView, send_dhis2_data

urlpatterns = [
    url(r'^map/$', DataSetMapListView.as_view(),
        name=DataSetMapListView.urlname),
    url(r'^send/$', send_dhis2_data, name='send_dhis2_data'),
]
