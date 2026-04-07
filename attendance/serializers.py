from rest_framework import serializers
from .models import Holiday, AttendanceLog, DailyAttendance, Permission


# ─────────────────────────────────────────────────────────────
# Holiday serializers
# ─────────────────────────────────────────────────────────────
class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = "__all__"


class HolidayCreateSerializer(serializers.Serializer):
    name               = serializers.CharField(max_length=255)
    day_type           = serializers.ChoiceField(choices=["HOLIDAY", "FESTIVAL"])
    group_id           = serializers.CharField(max_length=100, required=False, allow_blank=True)
    max_allowed_leaves = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    date               = serializers.DateField(required=False)
    dates              = serializers.ListField(
        child=serializers.DateField(),
        required=False,
        allow_empty=False,
    )

    def validate_group_id(self, value):
        return value.strip().upper() if value else value

    def validate(self, data):
        day_type = data.get("day_type")

        if day_type == "HOLIDAY":
            if not data.get("date"):
                raise serializers.ValidationError(
                    {"date": "A date is required for day_type HOLIDAY."}
                )

        elif day_type == "FESTIVAL":
            dates = data.get("dates")

            if not dates:
                raise serializers.ValidationError(
                    {"dates": "At least one date is required for day_type FESTIVAL."}
                )
            if not data.get("group_id"):
                raise serializers.ValidationError(
                    {"group_id": "group_id is required for day_type FESTIVAL."}
                )
            if data.get("max_allowed_leaves") is None:
                raise serializers.ValidationError(
                    {"max_allowed_leaves": "max_allowed_leaves is required for day_type FESTIVAL."}
                )
            if len(dates) != len(set(dates)):
                raise serializers.ValidationError(
                    {"dates": "Duplicate dates are not allowed in the same submission."}
                )

            existing = Holiday.objects.filter(date__in=dates).values_list("date", flat=True)
            if existing:
                existing_strs = [str(d) for d in existing]
                raise serializers.ValidationError(
                    {"dates": f"The following dates already exist: {', '.join(existing_strs)}"}
                )

        return data

    def create(self, validated_data):
        day_type           = validated_data["day_type"]
        name               = validated_data["name"]
        group_id           = validated_data.get("group_id") or ""
        max_allowed_leaves = validated_data.get("max_allowed_leaves")

        if day_type == "HOLIDAY":
            return Holiday.objects.create(
                name=name,
                date=validated_data["date"],
                day_type=day_type,
                group_id=group_id,
                max_allowed_leaves=max_allowed_leaves,
            )

        holidays = [
            Holiday(
                name=name,
                date=d,
                day_type=day_type,
                group_id=group_id,
                max_allowed_leaves=max_allowed_leaves,
            )
            for d in validated_data["dates"]
        ]
        return Holiday.objects.bulk_create(holidays)


# ─────────────────────────────────────────────────────────────
# Attendance serializers
# ─────────────────────────────────────────────────────────────
class AttendanceLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AttendanceLog
        fields = "__all__"


class DailyAttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyAttendance
        fields = "__all__"


# ─────────────────────────────────────────────────────────────
# Permission serializer
#   Read  → includes human-readable name fields the frontend
#           uses (employee_name, employee_id)
#   Write → accepts plain FK id (employee)
# ─────────────────────────────────────────────────────────────
class PermissionSerializer(serializers.ModelSerializer):
    # ── Read-only display fields ──────────────────────────────
    employee_name = serializers.SerializerMethodField()
    employee_id   = serializers.SerializerMethodField()   # the string ID e.g. "EMP001"

    class Meta:
        model  = Permission
        fields = [
            'id',
            'employee',          # FK id — used for write
            'employee_name',     # full name — read-only
            'employee_id',       # string employee id — read-only
            'date',
            'start_time',
            'end_time',
            'duration',
            'reason',
            'status',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'employee_name', 'employee_id']

    def get_employee_name(self, obj):
        try:
            return obj.employee.full_name if obj.employee_id else None
        except Exception:
            return None

    def get_employee_id(self, obj):
        # Returns the business-facing string id (e.g. "EMP001"), not the PK
        try:
            return obj.employee.employee_id if obj.employee_id else None
        except Exception:
            return None
        
from .models import OvertimeRecord

class OvertimeRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="attendance.employee.full_name", read_only=True)
    employee_id   = serializers.CharField(source="attendance.employee.employee_id", read_only=True)
    check_in      = serializers.DateTimeField(source="attendance.check_in",  read_only=True)
    check_out     = serializers.DateTimeField(source="attendance.check_out", read_only=True)
    total_hours   = serializers.DecimalField(source="attendance.total_hours", max_digits=5, decimal_places=2, read_only=True)
    date          = serializers.DateField(source="attendance.date", read_only=True)
    reviewed_by_name = serializers.CharField(source="reviewed_by.get_full_name", read_only=True, default=None)

    class Meta:
        model  = OvertimeRecord
        fields = [
            "id", "date",
            "employee_name", "employee_id",
            "check_in", "check_out", "total_hours",
            "extra_hours", "early_mins", "late_mins",
            "status", "reviewed_by_name", "reviewed_at", "created_at",
        ]