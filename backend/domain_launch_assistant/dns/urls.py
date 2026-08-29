# domain_launch_assistant/dns/urls.py

from django.urls import path

from domain_launch_assistant.dns.views import (
    CheckDomainView,
    DnsRecordCreateView,
    DnsRecordListView,
    DomainCheckListView,
)


urlpatterns = [
    path(
        "domains/<uuid:domain_id>/check/",
        CheckDomainView.as_view(),
        name="domain-check-start",
    ),
    path(
        "domains/<uuid:domain_id>/checks/",
        DomainCheckListView.as_view(),
        name="domain-check-list",
    ),
    path(
        "domains/<uuid:domain_id>/create-dns-record/",
        DnsRecordCreateView.as_view(),
        name="dns-record-create",
    ),
    path(
        "domains/<uuid:domain_id>/dns-records/",
        DnsRecordListView.as_view(),
        name="dns-record-list",
    ),
]