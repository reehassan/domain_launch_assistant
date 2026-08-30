# domain_launch_assistant/dns/serializers.py

from rest_framework import serializers

from domain_launch_assistant.dns.models import DomainCheck


class CheckDomainRequestSerializer(serializers.Serializer):
    """
    Validates the request body for POST /domains/{id}/check/
    Corresponds to api-contract.md section 20.

    Ticket 13: DNS_RESOLUTION used to PASS on any successful public DNS
    resolution, even for a domain this app never configured — a
    third-party server that happened to already occupy the hostname
    was enough to push a project to READY. There's no way to close that
    gap from *inside* the check itself: DnsRecordsService only ever
    writes to name.com's sandbox (see dns/services/dns_records.py), and
    a sandbox record can never affect real public DNS, since domains
    here are never actually registered (registration_simulation.py is
    simulation-only). So the check can't derive "what this app expects"
    on its own — the caller must supply it. `expected_value` is that
    input: the IP the founder actually pointed a real, owned domain's A
    record at for the demo. Required only when DNS_RESOLUTION is being
    requested — omitting it is now a 400, not a silent bare-resolution
    PASS.
    """

    check_types = serializers.ListField(
        child=serializers.ChoiceField(choices=DomainCheck.CheckType.choices),
        required=True,
        allow_empty=False,
    )
    expected_value = serializers.CharField(
        required=False, allow_blank=False, allow_null=True, default=None,
    )

    def validate_check_types(self, value):
        # De-dupe while preserving order, same way extensions get
        # normalized in DomainSearchRequestSerializer.
        seen = set()
        deduped = []
        for check_type in value:
            if check_type not in seen:
                seen.add(check_type)
                deduped.append(check_type)
        return deduped

    def validate(self, data):
        if (
            DomainCheck.CheckType.DNS_RESOLUTION in data["check_types"]
            and not data.get("expected_value")
        ):
            raise serializers.ValidationError(
                {
                    "expected_value": (
                        "expected_value is required when requesting a "
                        "DNS_RESOLUTION check — it must be the IP address "
                        "this domain's DNS is expected to resolve to."
                    )
                }
            )
        return data


class DomainCheckSerializer(serializers.ModelSerializer):
    """
    Read shape for GET /domains/{id}/checks/
    Corresponds to api-contract.md section 21.
    """

    class Meta:
        model = DomainCheck
        fields = [
            "id",
            "check_type",
            "status",
            "record_type",
            "record_name",
            "expected_value",
            "actual_value",
            "message",
            "checked_at",
        ]
        read_only_fields = fields


class DnsRecordCreateRequestSerializer(serializers.Serializer):
    """
    Validates the request body for POST /domains/{id}/create-dns-record/

    Field set matches name.com's documented DNSCreateRecordBody exactly
    (docs.name.com's DNS Create Record reference) — host, type, answer,
    ttl, priority. No local model backs this, so there's no
    ModelSerializer for the response side; the created Record dict
    comes straight back from name.com via the task result, same pattern
    simulate_registration_task already uses for its plain-dict result.
    """

    RECORD_TYPES = ["A", "AAAA", "ANAME", "CNAME", "MX", "NS", "SRV", "TXT"]

    host = serializers.CharField(required=False, allow_blank=True, default="")
    type = serializers.ChoiceField(choices=RECORD_TYPES, required=True)
    answer = serializers.CharField(required=True, allow_blank=False)
    ttl = serializers.IntegerField(required=False, default=300, min_value=300)
    priority = serializers.IntegerField(required=False, allow_null=True, default=None)

    def validate(self, data):
        # Per name.com's docs: priority is required for MX and SRV
        # records, ignored for all others.
        if data["type"] in ("MX", "SRV") and data.get("priority") is None:
            raise serializers.ValidationError(
                {"priority": "priority is required for MX and SRV records."}
            )
        return data