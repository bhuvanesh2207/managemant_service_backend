import re
import logging
from django.contrib.auth.models import User
from django.core.mail import send_mail, get_connection
from django.utils.crypto import get_random_string
from rest_framework import serializers
from .models import Employee, WorkShift, EmployeeShift
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# 🔹 WORK SHIFT
# ─────────────────────────────────────────
class WorkShiftSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkShift
        fields = ['id', 'name', 'start_time', 'end_time', 'break_hours', 'working_hours']

    def validate(self, data):
        start = data.get("start_time")
        end = data.get("end_time")
        break_hours = float(data.get("break_hours", 1))

        working_hours = data.get("working_hours")
        if working_hours is None:
            return data
        working_hours = float(working_hours)

        if start and end:
            start_datetime = datetime.combine(date.today(), start)

            if end < start:
                end_datetime = datetime.combine(date.today(), end) + timedelta(days=1)
            else:
                end_datetime = datetime.combine(date.today(), end)

            total_hours = (end_datetime - start_datetime).total_seconds() / 3600

            if working_hours > total_hours:
                raise serializers.ValidationError(
                    "Working hours cannot exceed total shift duration."
                )

            expected_hours = round(total_hours - break_hours, 2)

            if abs(working_hours - expected_hours) > 0.01:
                raise serializers.ValidationError(
                    f"Working hours should be {expected_hours} based on break time."
                )

        return data


# ─────────────────────────────────────────
# 🔹 EMPLOYEE SHIFT (inline, for nesting)
# ─────────────────────────────────────────
class EmployeeShiftInlineSerializer(serializers.ModelSerializer):
    shift_name = serializers.CharField(source='shift.name', read_only=True)

    class Meta:
        model = EmployeeShift
        fields = ['shift_name', 'start_date']


# ─────────────────────────────────────────
# 🔹 EMPLOYEE SHIFT (full, for ViewSet)
# ─────────────────────────────────────────
class EmployeeShiftSerializer(serializers.ModelSerializer):
    shift_name = serializers.CharField(source='shift.name', read_only=True)

    class Meta:
        model = EmployeeShift
        exclude = ['end_date']


# ─────────────────────────────────────────
# 🔹 EMPLOYEE — LIST / DETAIL
# ─────────────────────────────────────────
class EmployeeSerializer(serializers.ModelSerializer):
    photo_url        = serializers.SerializerMethodField()
    aadhaar_card_url = serializers.SerializerMethodField()
    pan_url          = serializers.SerializerMethodField()
    assigned_shift   = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = '__all__'

    def get_photo_url(self, obj):
        return obj.photo.url if obj.photo else None

    def get_aadhaar_card_url(self, obj):
        return obj.aadhaar_card.url if obj.aadhaar_card else None

    def get_pan_url(self, obj):
        return obj.pan.url if obj.pan else None

    def get_assigned_shift(self, obj):
        latest = (
            EmployeeShift.objects
            .filter(employee=obj)
            .select_related('shift')
            .order_by('-start_date')
            .first()
        )
        if latest:
            return {
                'shift_name':    latest.shift.name,
                'start_time':    str(latest.shift.start_time),
                'end_time':      str(latest.shift.end_time),
                'break_hours':   float(latest.shift.break_hours),
                'working_hours': float(latest.shift.working_hours),
                'start_date':    str(latest.start_date),
            }
        return None


# ─────────────────────────────────────────
# 🔹 EMPLOYEE — CREATE
# ─────────────────────────────────────────
class EmployeeCreateSerializer(serializers.ModelSerializer):
    user                     = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    employee_id              = serializers.CharField()
    full_name                = serializers.CharField()
    email                    = serializers.EmailField()
    blood_group              = serializers.ChoiceField(choices=Employee.BLOOD_GROUP_CHOICES)
    emergency_contact_person = serializers.CharField()
    emergency_contact_no     = serializers.CharField()
    emergency_relationship   = serializers.CharField()
    photo                    = serializers.ImageField()

    class Meta:
        model = Employee
        fields = '__all__'

    def validate_user(self, value):
        if value is None:
            return value
        if value.is_superuser:
            raise serializers.ValidationError("Superuser cannot be linked to an employee record.")
        if hasattr(value, 'employee_profile'):
            raise serializers.ValidationError("This user is already linked to another employee.")
        return value

    def validate_employee_id(self, value):
        if Employee.objects.filter(employee_id=value).exists():
            raise serializers.ValidationError("An employee with this ID already exists.")
        return value

    def validate_email(self, value):
        if Employee.objects.filter(email=value).exists():
            raise serializers.ValidationError("An employee with this email already exists.")
        return value

    def validate_account_number(self, value):
        if value and not value.isdigit():
            raise serializers.ValidationError("Account number must contain only digits.")
        return value

    def validate_ifsc_code(self, value):
        if value and not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', value.upper()):
            raise serializers.ValidationError("Enter a valid IFSC code (e.g. SBIN0001234).")
        return value.upper() if value else value

    def create(self, validated_data):
        from .services import create_employee_with_user
        return create_employee_with_user(validated_data)


# ─────────────────────────────────────────
# 🔹 EMPLOYEE — UPDATE
# ─────────────────────────────────────────
class EmployeeUpdateSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Employee
        fields = '__all__'

    def validate_user(self, value):
        if value is None:
            return value
        if value.is_superuser:
            raise serializers.ValidationError("Superuser cannot be linked to an employee record.")
        if hasattr(value, 'employee_profile') and value.employee_profile.id != self.instance.id:
            raise serializers.ValidationError("This user is already linked to another employee.")
        return value

    def validate_account_number(self, value):
        if value and not value.isdigit():
            raise serializers.ValidationError("Account number must contain only digits.")
        return value

    def validate_ifsc_code(self, value):
        if value and not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', value.upper()):
            raise serializers.ValidationError("Enter a valid IFSC code (e.g. SBIN0001234).")
        return value.upper() if value else value