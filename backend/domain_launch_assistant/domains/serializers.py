# domain_launch_assistant/domains/serializers.py

from rest_framework import serializers

from domain_launch_assistant.domains.models import (
    DomainClaim,
    DomainRecommendation,
    DomainResult,
    DomainSearch,
)

VALID_EXTENSIONS = {".com", ".ai", ".io", ".net", ".org", ".co", ".dev", ".app"}


class DomainSearchRequestSerializer(serializers.Serializer):
    """
    Validates the request body for POST /projects/{id}/domain-search/
    """

    brand_idea_id = serializers.UUIDField(required=True)
    extensions = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        allow_empty=False,
    )

    def validate_extensions(self, value):
        normalized = [ext.lower().strip() for ext in value]

        invalid = [ext for ext in normalized if ext not in VALID_EXTENSIONS]
        if invalid:
            raise serializers.ValidationError(
                f"Invalid domain extension(s): {', '.join(invalid)}"
            )

        return normalized


class DomainResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = DomainResult
        fields = [
            "id",
            "domain",
            "extension",
            "available",
            "status",
            "provider",
            "checked_at",
            "purchase_price",
            "renewal_price",
            "premium",
            "purchase_type",
        ]
        read_only_fields = fields


class DomainSearchSerializer(serializers.ModelSerializer):
    """
    Read shape for GET /projects/{id}/domain-searches/
    """

    brand_idea_id = serializers.UUIDField(source="brand_idea.id", read_only=True, allow_null=True)

    class Meta:
        model = DomainSearch
        fields = [
            "id",
            "brand_idea_id",
            "status",
            "requested_extensions",
            "started_at",
            "completed_at",
            "created_at",
        ]
        read_only_fields = fields


class SelectDomainSerializer(serializers.Serializer):
    """
    Validates the request body for POST /projects/{id}/select-domain/
    """

    domain_id = serializers.UUIDField(required=True)


class DomainRecommendationSerializer(serializers.ModelSerializer):
    """
    Read shape for GET /projects/{id}/domain-recommendations/
    """

    project_id = serializers.UUIDField(source="project.id", read_only=True)
    recommended_domain = DomainResultSerializer(read_only=True)

    class Meta:
        model = DomainRecommendation
        fields = [
            "id",
            "project_id",
            "recommended_domain",
            "reasoning",
            "created_at",
        ]
        read_only_fields = fields


class TogglePrivacySerializer(serializers.Serializer):
    """
    Validates the request body for POST /domains/{id}/toggle-privacy/
    """
    enabled = serializers.BooleanField(required=True)


class DomainClaimSerializer(serializers.ModelSerializer):
    """
    Read shape for GET /domains/{id}/claims/ — same shape convention as
    DomainCheckSerializer in the dns app.
    """

    domain_result_id = serializers.UUIDField(source="domain_result.id", read_only=True)

    class Meta:
        model = DomainClaim
        fields = [
            "id",
            "domain_result_id",
            "has_claims",
            "claims_data",
            "checked_at",
            "created_at",
        ]
        read_only_fields = fields