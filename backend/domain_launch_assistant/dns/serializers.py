# domain_launch_assistant/dns/serializers.py

from rest_framework import serializers

from domain_launch_assistant.dns.models import DomainCheck


class CheckDomainRequestSerializer(serializers.Serializer):
    """
    Validates the request body for POST /domains/{id}/check/
    Corresponds to api-contract.md section 20.
    """

    check_types = serializers.ListField(
        child=serializers.ChoiceField(choices=DomainCheck.CheckType.choices),
        required=True,
        allow_empty=False,
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