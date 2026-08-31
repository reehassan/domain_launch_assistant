# domain_launch_assistant/dns/urls.py
from django.urls import path

from domain_launch_assistant.dns.views import (
    CheckDomainView,
    DnsRecordCreateView,
    DnsRecordDeleteView,
    DnsRecordListView,
    DnsRecordUpdateView,
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
    path(
        "domains/<uuid:domain_id>/dns-records/<int:record_id>/update/",
        DnsRecordUpdateView.as_view(),
        name="dns-record-update",
    ),
    path(
        "domains/<uuid:domain_id>/dns-records/<int:record_id>/delete/",
        DnsRecordDeleteView.as_view(),
        name="dns-record-delete",
    ),
]