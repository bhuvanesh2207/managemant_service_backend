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
    changes_message = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )

    class Meta:
        model = Domain
        fields = [
            "client_name", "domain_name", "registrar",
            "purchase_date", "expiry_date", "active_status",
            "ssh_name", "ssh_purchase_date", "ssh_expiry_date",
            "hosting_name", "hosting_purchase_date", "hosting_expiry_date",
            "changes_message"
        ]

    def validate(self, attrs):
        purchase = attrs.get("purchase_date", self.instance.purchase_date)
        expiry = attrs.get("expiry_date", self.instance.expiry_date)

        if purchase and expiry and expiry <= purchase:
            raise serializers.ValidationError(
                {"expiry_date": "Expiry date must be after purchase date"}
            )

        ssh_name = attrs.get("ssh_name", self.instance.ssh_name)
        if ssh_name:
            ssh_purchase = attrs.get("ssh_purchase_date", self.instance.ssh_purchase_date)
            ssh_expiry = attrs.get("ssh_expiry_date", self.instance.ssh_expiry_date)
            if not ssh_purchase or not ssh_expiry:
                raise serializers.ValidationError(
                    "SSH dates are required when SSH is provided"
                )
            if ssh_expiry <= ssh_purchase:
                raise serializers.ValidationError(
                    "SSH expiry must be after SSH purchase date"
                )

        hosting_name = attrs.get("hosting_name", self.instance.hosting_name)
        if hosting_name:
            hosting_purchase = attrs.get(
                "hosting_purchase_date", self.instance.hosting_purchase_date
            )
            hosting_expiry = attrs.get(
                "hosting_expiry_date", self.instance.hosting_expiry_date
            )
            if not hosting_purchase or not hosting_expiry:
                raise serializers.ValidationError(
                    "Hosting dates are required when hosting is provided"
                )
            if hosting_expiry <= hosting_purchase:
                raise serializers.ValidationError(
                    "Hosting expiry must be after hosting purchase date"
                )

        return attrs


class DomainMiniSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ["id", "domain_name", "registrar"]

class DomainHistorySerializer(serializers.ModelSerializer):
    domain = DomainMiniSerializer(read_only=True)

    class Meta:
        model = DomainHistory
        fields = [
            "id",
            "domain",
            "changes",
            "updated_at",
            "updated_by",
        ]
