from rest_framework import serializers
from .models import Domain, DomainHistory

class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = [
            "id", "client_name", "domain_name", "registrar",
            "purchase_date", "expiry_date", "active_status",
            "ssh_name", "ssh_purchase_date", "ssh_expiry_date",
            "hosting_name", "hosting_purchase_date", "hosting_expiry_date"
        ]


class DomainCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = "__all__"

    def validate(self, attrs):
        if attrs.get("expiry_date") and attrs.get("purchase_date"):
            if attrs["expiry_date"] <= attrs["purchase_date"]:
                raise serializers.ValidationError("Expiry date must be after purchase date")

        # SSH validation
        if attrs.get("ssh_name"):
            if not attrs.get("ssh_purchase_date") or not attrs.get("ssh_expiry_date"):
                raise serializers.ValidationError("SSH dates are required when SSH is provided")
            if attrs["ssh_expiry_date"] <= attrs["ssh_purchase_date"]:
                raise serializers.ValidationError("SSH expiry must be after SSH purchase date")

        # Hosting validation
        if attrs.get("hosting_name"):
            if not attrs.get("hosting_purchase_date") or not attrs.get("hosting_expiry_date"):
                raise serializers.ValidationError("Hosting dates are required when hosting is provided")
            if attrs["hosting_expiry_date"] <= attrs["hosting_purchase_date"]:
                raise serializers.ValidationError("Hosting expiry must be after hosting purchase date")

        return attrs


class DomainUpdateSerializer(serializers.ModelSerializer):
    changes_message = serializers.CharField(write_only=True)

    class Meta:
        model = Domain
        fields = [
            "client_name", "domain_name", "registrar",
            "purchase_date", "expiry_date", "active_status",
            "ssh_name", "ssh_purchase_date", "ssh_expiry_date",
            "hosting_name", "hosting_purchase_date", "hosting_expiry_date",
            "changes_message"
        ]


class DomainHistorySerializer(serializers.ModelSerializer):
    domain_name = serializers.CharField(source="domain.domain_name", read_only=True)

    class Meta:
        model = DomainHistory
        fields = ["id", "domain", "domain_name", "changes", "updated_at", "updated_by"]
