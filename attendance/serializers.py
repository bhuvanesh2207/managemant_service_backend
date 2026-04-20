import math
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from rest_framework import serializers
from .models import (
    Holiday,
    AttendanceLog,
    DailyAttendance,
    EmployeePermission,
    OvertimeRecord,
    OvertimeRequest,
    Leave,
)


# ═════════════════════════════════════════════════════════════
#  HOLIDAY SERIALIZERS
# ═════════════════════════════════════════════════════════════

class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = '__all__'


class HolidayCreateSerializer(serializers.ModelSerializer):
    is_festival = serializers.BooleanField(default=False, write_only=True)
    end_date    = serializers.DateField(required=False, write_only=True)

    class Meta:
        model = Holiday
        fields = [
            'name', 'date', 'day_type', 'group_id', 'max_allowed_leaves',
            'is_festival', 'end_date',
        ]

    def create(self, validated_data):
        is_festival = validated_data.pop('is_festival', False)
        end_date    = validated_data.pop('end_date', None)

        if is_festival and end_date:
            # Create multiple holidays for festival date range
            start = validated_data['date']
            end = end_date
            group_id = validated_data.get('group_id') or f"FEST_{start.strftime('%Y%m%d')}"
            
            holidays = []
            current = start
            while current <= end:
                holidays.append(Holiday(
                    name=validated_data['name'],
                    date=current,
                    day_type='FESTIVAL',
                    group_id=group_id,
                    max_allowed_leaves=validated_data.get('max_allowed_leaves'),
                ))
                current += timedelta(days=1)
            
            Holiday.objects.bulk_create(holidays)
            return holidays
        
        return Holiday.objects.create(**validated_data)


# ═════════════════════════════════════════════════════════════
#  ATTENDANCE LOG SERIALIZERS
# ═════════════════════════════════════════════════════════════

class AttendanceLogSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)

    class Meta:
        model = AttendanceLog
        fields = '__all__'


class DailyAttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    
    class Meta:
        model = DailyAttendance
        fields = '__all__'


# ═════════════════════════════════════════════════════════════
#  OVERTIME RECORD SERIALIZER
# ═════════════════════════════════════════════════════════════

class OvertimeRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='attendance.employee.full_name', read_only=True)
    date          = serializers.DateField(source='attendance.date', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = OvertimeRecord
        fields = '__all__'

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None


# ═════════════════════════════════════════════════════════════
#  OVERTIME REQUEST SERIALIZERS (UPDATED)
# ═════════════════════════════════════════════════════════════

class OvertimeRequestSerializer(serializers.ModelSerializer):
    """
    Read serializer — used in all responses (list, detail, post-action).
    """
    employee_name    = serializers.CharField(source='employee.full_name',   read_only=True)
    employee_code    = serializers.CharField(source='employee.employee_id', read_only=True)
    total_days       = serializers.IntegerField(read_only=True)
    daily_hours      = serializers.FloatField(read_only=True)
    total_hours      = serializers.FloatField(read_only=True)
    can_modify       = serializers.BooleanField(read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    created_by_name  = serializers.SerializerMethodField()

    # Audit chain
    replaced_by_id = serializers.PrimaryKeyRelatedField(source='replaced_by', read_only=True)
    replaces_id    = serializers.SerializerMethodField()

    class Meta:
        model  = OvertimeRequest
        fields = [
            'id',
            'employee',
            'employee_name',
            'employee_code',
            'start_date',
            'end_date',
            'total_days',
            'time_slots',
            'daily_hours',
            'total_hours',
            'reason',
            'notes',
            'source',
            'status',
            'is_active',
            'can_modify',
            'replaced_by_id',
            'replaces_id',
            'reviewed_by',
            'reviewed_by_name',
            'reviewed_at',
            'admin_remarks',
            'created_by',
            'created_by_name',
            'created_at',
        ]
        read_only_fields = fields

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name() or obj.created_by.username
        return None

    def get_replaces_id(self, obj):
        if hasattr(obj, 'replaces') and obj.replaces:
            return obj.replaces.id
        return None


class TimeSlotSerializer(serializers.Serializer):
    """Serializer for individual time slots."""
    start_time = serializers.TimeField(format='%H:%M')
    end_time = serializers.TimeField(format='%H:%M')

    def validate(self, data):
        start_time = data['start_time']
        end_time = data['end_time']
        
        if start_time >= end_time:
            raise serializers.ValidationError("End time must be after start time.")
        
        return data


class OvertimeRequestSubmitSerializer(serializers.Serializer):
    """
    Employee submits an OT request for a date range with multiple time slots.
    """
    start_date = serializers.DateField()
    end_date   = serializers.DateField()
    time_slots = serializers.ListField(
        child=TimeSlotSerializer(),
        min_length=1,
        max_length=10
    )
    reason     = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_start_date(self, value):
        if value < timezone.localdate():
            raise serializers.ValidationError("OT start date cannot be in the past.")
        return value

    def validate(self, data):
        start_date = data['start_date']
        end_date   = data['end_date']
        time_slots = data['time_slots']

        if end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )

        # Validate no overlapping slots within the request
        slots = time_slots
        for i in range(len(slots)):
            for j in range(i + 1, len(slots)):
                slot1, slot2 = slots[i], slots[j]
                
                def time_to_minutes(t):
                    return t.hour * 60 + t.minute
                
                s1_start = time_to_minutes(slot1['start_time'])
                s1_end = time_to_minutes(slot1['end_time'])
                s2_start = time_to_minutes(slot2['start_time'])
                s2_end = time_to_minutes(slot2['end_time'])
                
                if s1_end <= s1_start:
                    s1_end += 24 * 60
                if s2_end <= s2_start:
                    s2_end += 24 * 60
                    
                if max(s1_start, s2_start) < min(s1_end, s2_end):
                    raise serializers.ValidationError(
                        {"time_slots": f"Time slots overlap: {slot1['start_time']}-{slot1['end_time']} and {slot2['start_time']}-{slot2['end_time']}"}
                    )

        # Check for overlapping existing requests
        employee = self.context['employee']
        overlapping_requests = OvertimeRequest.objects.filter(
            employee=employee,
            is_active=True,
            status__in=[OvertimeRequest.STATUS_PENDING, OvertimeRequest.STATUS_APPROVED],
        ).filter(
            start_date__lte=end_date,
            end_date__gte=start_date,
        )

        if overlapping_requests.exists():
            for existing_req in overlapping_requests:
                overlap_found = self._check_detailed_overlap(
                    start_date, end_date, time_slots, existing_req
                )
                if overlap_found:
                    raise serializers.ValidationError(
                        "An active OT request already exists overlapping this date range and time slots. "
                        "Wait for admin review or contact your admin."
                    )

        return data

    def _check_detailed_overlap(self, new_start, new_end, new_slots, existing_req):
        new_dates = self._daterange(new_start, new_end)
        existing_dates = self._daterange(existing_req.start_date, existing_req.end_date)
        
        common_dates = set(new_dates) & set(existing_dates)
        
        if not common_dates:
            return False
            
        for new_slot in new_slots:
            for existing_slot in existing_req.time_slots:
                if self._slots_overlap(new_slot, existing_slot):
                    return True
                    
        return False

    def _daterange(self, start_date, end_date):
        for n in range((end_date - start_date).days + 1):
            yield start_date + timedelta(days=n)

    def _slots_overlap(self, slot1, slot2):
        def time_to_minutes(t):
            if isinstance(t, str):
                h, m = map(int, t.split(':'))
                return h * 60 + m
            return t.hour * 60 + t.minute
            
        s1_start = time_to_minutes(slot1['start_time'])
        s1_end = time_to_minutes(slot1['end_time'])
        s2_start = time_to_minutes(slot2['start_time'])
        s2_end = time_to_minutes(slot2['end_time'])
        
        if s1_end <= s1_start:
            s1_end += 24 * 60
        if s2_end <= s2_start:
            s2_end += 24 * 60
            
        return max(s1_start, s2_start) < min(s1_end, s2_end)

    def create(self, validated_data):
        employee   = self.context['employee']
        created_by = self.context['request'].user
        
        time_slots_data = validated_data['time_slots']
        time_slots_serialized = []
        
        for slot in time_slots_data:
            time_slots_serialized.append({
                'start_time': slot['start_time'].strftime('%H:%M'),
                'end_time': slot['end_time'].strftime('%H:%M')
            })
        
        return OvertimeRequest.objects.create(
            employee   = employee,
            start_date = validated_data['start_date'],
            end_date   = validated_data['end_date'],
            time_slots = time_slots_serialized,
            reason     = validated_data.get('reason', ''),
            source     = OvertimeRequest.SOURCE_EMPLOYEE,
            status     = OvertimeRequest.STATUS_PENDING,
            is_active  = True,
            created_by = created_by,
        )


class OvertimeRequestModifySerializer(serializers.Serializer):
    """
    Admin modifies an employee-submitted PENDING OT request.
    """
    start_date = serializers.DateField(required=False)
    end_date   = serializers.DateField(required=False)
    time_slots = serializers.ListField(
        child=TimeSlotSerializer(),
        required=False
    )
    reason     = serializers.CharField(required=False, allow_blank=True)
    notes      = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        ot = self.context['ot_request']

        if ot.source == OvertimeRequest.SOURCE_EMPLOYEE and ot.status != OvertimeRequest.STATUS_PENDING:
            raise serializers.ValidationError(
                f"This OT request is already {ot.status}. "
                "Approved requests are locked and cannot be modified."
            )

        if not ot.is_active:
            raise serializers.ValidationError(
                "This record has already been superseded and cannot be modified."
            )

        start_date = data.get('start_date', ot.start_date)
        end_date   = data.get('end_date',   ot.end_date)
        time_slots = data.get('time_slots', ot.time_slots)

        if end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )

        if 'time_slots' in data:
            slots = time_slots
            for i in range(len(slots)):
                for j in range(i + 1, len(slots)):
                    slot1, slot2 = slots[i], slots[j]
                    
                    def time_to_minutes(t):
                        if isinstance(t, str):
                            h, m = map(int, t.split(':'))
                            return h * 60 + m
                        return t.hour * 60 + t.minute
                    
                    s1_start = time_to_minutes(slot1['start_time'])
                    s1_end = time_to_minutes(slot1['end_time'])
                    s2_start = time_to_minutes(slot2['start_time'])
                    s2_end = time_to_minutes(slot2['end_time'])
                    
                    if s1_end <= s1_start:
                        s1_end += 24 * 60
                    if s2_end <= s2_start:
                        s2_end += 24 * 60
                        
                    if max(s1_start, s2_start) < min(s1_end, s2_end):
                        raise serializers.ValidationError(
                            {"time_slots": "Time slots cannot overlap within the same request."}
                        )

        return data

    def save(self, **kwargs):
        ot         = self.context['ot_request']
        admin_user = self.context['request'].user
        data       = self.validated_data

        ot.is_active = False
        ot.save(update_fields=['is_active'])

        time_slots_data = data.get('time_slots', ot.time_slots)
        if 'time_slots' in data:
            time_slots_serialized = []
            for slot in time_slots_data:
                time_slots_serialized.append({
                    'start_time': slot['start_time'].strftime('%H:%M'),
                    'end_time': slot['end_time'].strftime('%H:%M')
                })
        else:
            time_slots_serialized = time_slots_data

        new_ot = OvertimeRequest.objects.create(
            employee      = ot.employee,
            start_date    = data.get('start_date', ot.start_date),
            end_date      = data.get('end_date',   ot.end_date),
            time_slots    = time_slots_serialized,
            reason        = data.get('reason',     ot.reason),
            notes         = data.get('notes',      ot.notes),
            source        = OvertimeRequest.SOURCE_EMPLOYEE,
            status        = OvertimeRequest.STATUS_PENDING,
            is_active     = True,
            created_by    = admin_user,
            admin_remarks = f"Modified by admin: {admin_user.get_full_name() or admin_user.username}",
        )

        ot.replaced_by = new_ot
        ot.save(update_fields=['replaced_by'])

        return new_ot


class OvertimeRequestReviewSerializer(serializers.Serializer):
    """
    Admin approves or declines a pending OT request.
    """
    status = serializers.ChoiceField(
        choices=[OvertimeRequest.STATUS_APPROVED, OvertimeRequest.STATUS_DECLINED]
    )
    admin_remarks = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        ot = self.context['ot_request']

        if ot.status != OvertimeRequest.STATUS_PENDING:
            raise serializers.ValidationError(
                f"This OT request is already {ot.status}. Cannot review again."
            )

        if not ot.is_active:
            raise serializers.ValidationError(
                "This record has already been superseded and cannot be reviewed."
            )

        return data

    def save(self, **kwargs):
        ot         = self.context['ot_request']
        admin_user = self.context['request'].user
        data       = self.validated_data

        ot.is_active = False
        ot.save(update_fields=['is_active'])

        new_ot = OvertimeRequest.objects.create(
            employee      = ot.employee,
            start_date    = ot.start_date,
            end_date      = ot.end_date,
            time_slots    = ot.time_slots,
            reason        = ot.reason,
            notes         = ot.notes,
            source        = ot.source,
            status        = data['status'],
            is_active     = True,
            created_by    = ot.created_by,
            reviewed_by   = admin_user,
            reviewed_at   = timezone.now(),
            admin_remarks = data.get('admin_remarks', ''),
        )

        ot.replaced_by = new_ot
        ot.save(update_fields=['replaced_by'])

        return new_ot


class OvertimeRequestAssignSerializer(serializers.Serializer):
    """
    Admin assigns OT to one or more employees directly.
    """
    employee_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
        help_text="List of Employee PKs to assign OT to.",
    )
    start_date = serializers.DateField()
    end_date   = serializers.DateField()
    time_slots = serializers.ListField(
        child=TimeSlotSerializer(),
        min_length=1,
        max_length=10
    )
    reason     = serializers.CharField(required=False, allow_blank=True, default='')
    notes      = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, data):
        from employee.models import Employee as EmployeeModel

        employee_ids = data['employee_ids']
        found   = EmployeeModel.objects.filter(pk__in=employee_ids).values_list('pk', flat=True)
        missing = set(employee_ids) - set(found)
        if missing:
            raise serializers.ValidationError(
                {"employee_ids": f"Employees not found: {sorted(missing)}"}
            )

        if data['end_date'] < data['start_date']:
            raise serializers.ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )

        time_slots = data['time_slots']
        for i in range(len(time_slots)):
            for j in range(i + 1, len(time_slots)):
                slot1, slot2 = time_slots[i], time_slots[j]
                
                def time_to_minutes(t):
                    return t.hour * 60 + t.minute
                
                s1_start = time_to_minutes(slot1['start_time'])
                s1_end = time_to_minutes(slot1['end_time'])
                s2_start = time_to_minutes(slot2['start_time'])
                s2_end = time_to_minutes(slot2['end_time'])
                
                if s1_end <= s1_start:
                    s1_end += 24 * 60
                if s2_end <= s2_start:
                    s2_end += 24 * 60
                    
                if max(s1_start, s2_start) < min(s1_end, s2_end):
                    raise serializers.ValidationError(
                        {"time_slots": "Time slots cannot overlap within the same request."}
                    )

        return data

    def create(self, validated_data):
        from employee.models import Employee as EmployeeModel

        admin_user   = self.context['request'].user
        employee_ids = validated_data['employee_ids']
        employees    = EmployeeModel.objects.filter(pk__in=employee_ids)
        created      = []

        time_slots_data = validated_data['time_slots']
        time_slots_serialized = []
        for slot in time_slots_data:
            time_slots_serialized.append({
                'start_time': slot['start_time'].strftime('%H:%M'),
                'end_time': slot['end_time'].strftime('%H:%M')
            })

        for employee in employees:
            existing = OvertimeRequest.objects.filter(
                employee   = employee,
                is_active  = True,
                start_date__lte = validated_data['end_date'],
                end_date__gte   = validated_data['start_date'],
            ).first()

            new_ot = OvertimeRequest.objects.create(
                employee    = employee,
                start_date  = validated_data['start_date'],
                end_date    = validated_data['end_date'],
                time_slots  = time_slots_serialized,
                reason      = validated_data.get('reason', ''),
                notes       = validated_data.get('notes', ''),
                source      = OvertimeRequest.SOURCE_ADMIN,
                status      = OvertimeRequest.STATUS_APPROVED,
                is_active   = True,
                created_by  = admin_user,
                reviewed_by = admin_user,
                reviewed_at = timezone.now(),
            )

            if existing:
                existing.is_active   = False
                existing.replaced_by = new_ot
                existing.save(update_fields=['is_active', 'replaced_by'])

            created.append(new_ot)

        return created


class OvertimeRequestAdminUpdateSerializer(serializers.Serializer):
    """
    Admin updates a previously admin-assigned OT record.
    """
    start_date = serializers.DateField(required=False)
    end_date   = serializers.DateField(required=False)
    time_slots = serializers.ListField(
        child=TimeSlotSerializer(),
        required=False
    )
    reason     = serializers.CharField(required=False, allow_blank=True)
    notes      = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        ot = self.context['ot_request']

        if ot.source != OvertimeRequest.SOURCE_ADMIN:
            raise serializers.ValidationError(
                "Use the /modify/ endpoint for employee-submitted requests."
            )
        if not ot.is_active:
            raise serializers.ValidationError(
                "This record has already been superseded. Cannot update."
            )

        start_date = data.get('start_date', ot.start_date)
        end_date   = data.get('end_date',   ot.end_date)

        if end_date < start_date:
            raise serializers.ValidationError(
                {"end_date": "end_date must be on or after start_date."}
            )

        if 'time_slots' in data:
            time_slots = data['time_slots']
            for i in range(len(time_slots)):
                for j in range(i + 1, len(time_slots)):
                    slot1, slot2 = time_slots[i], time_slots[j]
                    
                    def time_to_minutes(t):
                        return t.hour * 60 + t.minute
                    
                    s1_start = time_to_minutes(slot1['start_time'])
                    s1_end = time_to_minutes(slot1['end_time'])
                    s2_start = time_to_minutes(slot2['start_time'])
                    s2_end = time_to_minutes(slot2['end_time'])
                    
                    if s1_end <= s1_start:
                        s1_end += 24 * 60
                    if s2_end <= s2_start:
                        s2_end += 24 * 60
                        
                    if max(s1_start, s2_start) < min(s1_end, s2_end):
                        raise serializers.ValidationError(
                            {"time_slots": "Time slots cannot overlap within the same request."}
                        )

        return data

    def save(self, **kwargs):
        ot         = self.context['ot_request']
        admin_user = self.context['request'].user
        data       = self.validated_data

        ot.is_active = False
        ot.save(update_fields=['is_active'])

        time_slots_data = data.get('time_slots', ot.time_slots)
        if 'time_slots' in data:
            time_slots_serialized = []
            for slot in time_slots_data:
                time_slots_serialized.append({
                    'start_time': slot['start_time'].strftime('%H:%M'),
                    'end_time': slot['end_time'].strftime('%H:%M')
                })
        else:
            time_slots_serialized = time_slots_data

        new_ot = OvertimeRequest.objects.create(
            employee    = ot.employee,
            start_date  = data.get('start_date', ot.start_date),
            end_date    = data.get('end_date',   ot.end_date),
            time_slots  = time_slots_serialized,
            reason      = data.get('reason',     ot.reason),
            notes       = data.get('notes',      ot.notes),
            source      = OvertimeRequest.SOURCE_ADMIN,
            status      = OvertimeRequest.STATUS_APPROVED,
            is_active   = True,
            created_by  = admin_user,
            reviewed_by = admin_user,
            reviewed_at = timezone.now(),
        )

        ot.replaced_by = new_ot
        ot.save(update_fields=['replaced_by'])

        return new_ot


# ═════════════════════════════════════════════════════════════
#  EMPLOYEE PERMISSION SERIALIZERS
# ═════════════════════════════════════════════════════════════

class EmployeePermissionSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = EmployeePermission
        fields = '__all__'

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None


class EmployeePermissionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeePermission
        fields = ['date', 'permission_type', 'request_type', 'reason', 'expected_end_time']

    def create(self, validated_data):
        employee = self.context['employee']
        return EmployeePermission.objects.create(
            employee=employee,
            status=EmployeePermission.STATUS_ACTIVE if validated_data['request_type'] == EmployeePermission.REQUEST_EMERGENCY 
                   else EmployeePermission.STATUS_PENDING,
            **validated_data
        )


class EmployeePermissionReviewSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[EmployeePermission.STATUS_APPROVED, EmployeePermission.STATUS_REJECTED]
    )
    admin_remarks = serializers.CharField(required=False, allow_blank=True)


class EmployeePermissionCompleteSerializer(serializers.Serializer):
    latitude  = serializers.FloatField()
    longitude = serializers.FloatField()
    image     = serializers.ImageField(required=False, allow_null=True)

    def save(self, **kwargs):
        perm = self.context['permission']
        data = self.validated_data
        
        perm.actual_end_time = timezone.now()
        perm.return_latitude = data['latitude']
        perm.return_longitude = data['longitude']
        
        if data.get('image'):
            perm.return_image = data['image']
        
        perm.location_valid = perm.is_within_office(data['latitude'], data['longitude'])
        
        if perm.location_valid:
            perm.status = EmployeePermission.STATUS_COMPLETED
            if perm.start_time:
                duration = (perm.actual_end_time - perm.start_time).total_seconds() / 3600
                perm.duration = round(duration, 2)
        else:
            perm.status = EmployeePermission.STATUS_REJECTED
            perm.admin_remarks = "Location validation failed - outside office radius."
        
        perm.save()
        return perm


# ═════════════════════════════════════════════════════════════
#  LEAVE SERIALIZERS
# ═════════════════════════════════════════════════════════════

class LeaveSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    total_days = serializers.SerializerMethodField()

    class Meta:
        model = Leave
        fields = '__all__'

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None

    def get_total_days(self, obj):
        return (obj.end_date - obj.start_date).days + 1


class LeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Leave
        fields = ['start_date', 'end_date', 'reason', 'leave_type']

    def validate(self, data):
        if data['end_date'] < data['start_date']:
            raise serializers.ValidationError(
                {"end_date": "End date must be on or after start date."}
            )
        return data

    def create(self, validated_data):
        employee = self.context['employee']
        return Leave.objects.create(
            employee=employee,
            status='PENDING',
            **validated_data
        )


class LeaveUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=['APPROVED', 'REJECTED']
    )
    admin_remarks = serializers.CharField(required=False, allow_blank=True)