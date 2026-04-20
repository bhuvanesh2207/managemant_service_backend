import math
from datetime import datetime, timedelta, date as date_type

from django.db import models
from django.conf import settings
from django.contrib.auth.models import User
from employee.models import Employee


class Holiday(models.Model):
    DAY_TYPE_CHOICES = [
        ('HOLIDAY', 'Holiday'),
        ('FESTIVAL', 'Festival'),
    ]

    name               = models.CharField(max_length=255)
    date               = models.DateField()
    day_type           = models.CharField(max_length=10, choices=DAY_TYPE_CHOICES)
    group_id           = models.CharField(max_length=100, blank=True, null=True)
    max_allowed_leaves = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ['date']
        db_table = 'attendance_holiday'

    def __str__(self):
        return f"{self.name} ({self.date}) — {self.day_type}"


class AttendanceLog(models.Model):
    employee       = models.ForeignKey(Employee, on_delete=models.CASCADE)
    device_user_id = models.CharField(max_length=50)
    timestamp      = models.DateTimeField()
    status         = models.IntegerField()
    created_at     = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee} - {self.timestamp}"


class DailyAttendance(models.Model):
    employee    = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date        = models.DateField()
    check_in    = models.DateTimeField(null=True, blank=True)
    check_out   = models.DateTimeField(null=True, blank=True)
    total_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    extra_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    ot_eligible = models.BooleanField(default=False)

    STATUS = [
        ('present',  'Present'),
        ('absent',   'Absent'),
        ('half_day', 'Half Day'),
    ]
    status = models.CharField(max_length=20, choices=STATUS)

    class Meta:
        unique_together = ('employee', 'date')

    def __str__(self):
        return f"{self.employee} - {self.date}"


class EmployeePermission(models.Model):

    TYPE_MID_DAY = 'MID_DAY'
    TYPE_END_DAY = 'END_DAY'
    TYPE_CHOICES = [
        (TYPE_MID_DAY, 'Mid Day'),
        (TYPE_END_DAY, 'End Day'),
    ]

    REQUEST_EMERGENCY  = 'EMERGENCY'
    REQUEST_PREPLANNED = 'PREPLANNED'
    REQUEST_TYPE_CHOICES = [
        (REQUEST_EMERGENCY,  'Emergency'),
        (REQUEST_PREPLANNED, 'Pre-planned'),
    ]

    STATUS_PENDING   = 'PENDING'
    STATUS_APPROVED  = 'APPROVED'
    STATUS_ACTIVE    = 'ACTIVE'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_REJECTED  = 'REJECTED'
    STATUS_CHOICES   = [
        (STATUS_PENDING,   'Pending'),
        (STATUS_APPROVED,  'Approved'),
        (STATUS_ACTIVE,    'Active'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_REJECTED,  'Rejected'),
    ]

    FLAG_OK       = 'OK'
    FLAG_OVERUSED = 'OVERUSED'
    FLAG_CHOICES  = [
        (FLAG_OK,       'Ok'),
        (FLAG_OVERUSED, 'Overused'),
    ]

    employee          = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date              = models.DateField()
    permission_type   = models.CharField(max_length=10, choices=TYPE_CHOICES)
    request_type      = models.CharField(
        max_length=12,
        choices=REQUEST_TYPE_CHOICES,
        default=REQUEST_EMERGENCY,
    )
    reason            = models.TextField()
    expected_end_time = models.DateTimeField()

    start_time        = models.DateTimeField(null=True, blank=True)
    actual_end_time   = models.DateTimeField(null=True, blank=True)
    duration          = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    return_image      = models.ImageField(upload_to='permissions/', null=True, blank=True)
    return_latitude   = models.FloatField(null=True, blank=True)
    return_longitude  = models.FloatField(null=True, blank=True)
    location_valid    = models.BooleanField(null=True, blank=True)

    status     = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE)
    usage_flag = models.CharField(max_length=10, choices=FLAG_CHOICES, null=True, blank=True)

    reviewed_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_permissions',
    )
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    admin_remarks = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    OFFICE_LATITUDE  = 0.0
    OFFICE_LONGITUDE = 0.0
    OFFICE_RADIUS_KM = 0.1

    def is_within_office(self, lat, lon):
        R    = 6371
        dlat = math.radians(lat - self.OFFICE_LATITUDE)
        dlon = math.radians(lon - self.OFFICE_LONGITUDE)
        a    = (math.sin(dlat / 2) ** 2 +
                math.cos(math.radians(self.OFFICE_LATITUDE)) *
                math.cos(math.radians(lat)) *
                math.sin(dlon / 2) ** 2)
        return 2 * R * math.asin(math.sqrt(a)) <= self.OFFICE_RADIUS_KM

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee} — {self.permission_type} on {self.date} ({self.status})"


class OvertimeRecord(models.Model):
    STATUS_PENDING  = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DECLINED = "declined"
    STATUS_CHOICES  = [
        (STATUS_PENDING,  "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DECLINED, "Declined"),
    ]

    attendance  = models.OneToOneField(
        DailyAttendance, on_delete=models.CASCADE, related_name="overtime"
    )
    extra_hours = models.DecimalField(max_digits=5, decimal_places=2)
    early_mins  = models.PositiveIntegerField(default=0)
    late_mins   = models.PositiveIntegerField(default=0)
    status      = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="ot_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-attendance__date"]

    def __str__(self):
        return f"{self.attendance.employee} – {self.extra_hours}h ({self.status})"


class Leave(models.Model):
    STATUS_CHOICES = [
        ('PENDING',  'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    LEAVE_TYPE_CHOICES = [
        ('CASUAL', 'Casual Leave'),
        ('SICK',   'Sick Leave'),
        ('EARNED', 'Earned Leave'),
        ('UNPAID', 'Unpaid Leave'),
    ]

    employee      = models.ForeignKey(Employee, on_delete=models.CASCADE)
    start_date    = models.DateField()
    end_date      = models.DateField()
    reason        = models.TextField()
    status        = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    leave_type    = models.CharField(max_length=10, choices=LEAVE_TYPE_CHOICES, default='CASUAL')
    applied_at    = models.DateTimeField(auto_now_add=True)
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    reviewed_by   = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_leaves',
    )
    admin_remarks = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.employee.full_name} - {self.status}"


# ═══════════════════════════════════════════════════════════════════════════
#  OVERTIME REQUEST  (Scenario 1 — Employee, Scenario 2 — Admin)
# ═══════════════════════════════════════════════════════════════════════════

class OvertimeRequest(models.Model):
    STATUS_PENDING  = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_DECLINED = 'declined'
    STATUS_CHOICES  = [
        (STATUS_PENDING,  'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_DECLINED, 'Declined'),
    ]

    SOURCE_EMPLOYEE = 'employee'
    SOURCE_ADMIN    = 'admin'
    SOURCE_CHOICES  = [
        (SOURCE_EMPLOYEE, 'Employee'),
        (SOURCE_ADMIN,    'Admin'),
    ]

    employee   = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='overtime_requests',
    )

    start_date = models.DateField(help_text="First day of OT range")
    end_date   = models.DateField(help_text="Last day of OT range (inclusive)")
    
    time_slots = models.JSONField(
        default=list,
        help_text="List of time slots. Format: [{'start_time': 'HH:MM', 'end_time': 'HH:MM'}, ...]"
    )

    reason = models.TextField(blank=True, default='')
    notes  = models.TextField(
        blank=True, default='',
        help_text="Admin-side notes (visible to admin only)",
    )

    total_hours = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Automatically calculated total hours"
    )

    source    = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_EMPLOYEE)
    status    = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    is_active = models.BooleanField(
        default=True,
        help_text="False = superseded by a newer record. Never physically deleted.",
    )

    replaced_by = models.OneToOneField(
        'self',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='replaces',
        help_text="When this record is disabled, points to the new record that replaced it.",
    )

    reviewed_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='ot_request_reviews',
    )
    reviewed_at   = models.DateTimeField(null=True, blank=True)
    admin_remarks = models.TextField(blank=True, default='')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='ot_requests_created',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        db_table = 'attendance_overtime_request'

    def __str__(self):
        state = "active" if self.is_active else "disabled"
        slots_count = len(self.time_slots) if self.time_slots else 0
        return (
            f"{self.employee} | {self.start_date}→{self.end_date} | "
            f"{slots_count} slot(s) | {self.total_hours}h | "
            f"source={self.source} status={self.status} [{state}]"
        )

    @property
    def total_days(self) -> int:
        if not self.start_date or not self.end_date:
            return 0
        return (self.end_date - self.start_date).days + 1

    @staticmethod
    def _calculate_slot_hours(start_time_str: str, end_time_str: str) -> float:
        start_time = datetime.strptime(start_time_str, '%H:%M').time()
        end_time = datetime.strptime(end_time_str, '%H:%M').time()
        
        dt_start = datetime.combine(date_type.today(), start_time)
        dt_end = datetime.combine(date_type.today(), end_time)
        
        if dt_end <= dt_start:
            dt_end += timedelta(days=1)
            
        return round((dt_end - dt_start).total_seconds() / 3600, 2)

    @property
    def daily_hours(self) -> float:
        if not self.time_slots:
            return 0.0
        
        total_daily = 0.0
        for slot in self.time_slots:
            total_daily += self._calculate_slot_hours(slot['start_time'], slot['end_time'])
        
        return round(total_daily, 2)

    def calculate_total_hours(self) -> float:
        if not self.time_slots or not self.start_date or not self.end_date:
            return 0.0
            
        daily_hours = self.daily_hours
        return round(daily_hours * self.total_days, 2)

    def save(self, *args, **kwargs):
        if self.time_slots and self.start_date and self.end_date:
            self.total_hours = self.calculate_total_hours()
        super().save(*args, **kwargs)

    @property
    def can_modify(self) -> bool:
        if not self.is_active:
            return False
        if self.source == self.SOURCE_EMPLOYEE:
            return self.status == self.STATUS_PENDING
        return True

    @staticmethod
    def _time_to_minutes(time_str: str) -> int:
        h, m = map(int, time_str.split(':'))
        return h * 60 + m

    def _slots_overlap(self, slot1: dict, slot2: dict) -> bool:
        s1_start = self._time_to_minutes(slot1['start_time'])
        s1_end = self._time_to_minutes(slot1['end_time'])
        s2_start = self._time_to_minutes(slot2['start_time'])
        s2_end = self._time_to_minutes(slot2['end_time'])
        
        if s1_end <= s1_start:
            s1_end += 24 * 60
        if s2_end <= s2_start:
            s2_end += 24 * 60
            
        return max(s1_start, s2_start) < min(s1_end, s2_end)

    def validate_time_slots(self) -> bool:
        if not self.time_slots:
            return True
            
        slots = self.time_slots
        for i in range(len(slots)):
            for j in range(i + 1, len(slots)):
                if self._slots_overlap(slots[i], slots[j]):
                    return False
        return True

    def get_overlapping_requests(self):
        from django.db.models import Q
        
        if not self.start_date or not self.end_date:
            return OvertimeRequest.objects.none()
        
        return OvertimeRequest.objects.filter(
            employee=self.employee,
            is_active=True,
            status__in=[self.STATUS_PENDING, self.STATUS_APPROVED],
        ).filter(
            Q(start_date__lte=self.end_date) & Q(end_date__gte=self.start_date)
        ).exclude(pk=self.pk if self.pk else None)

    def check_overlap_with_existing(self, other_request) -> bool:
        if not self.time_slots or not other_request.time_slots:
            return False
        
        overlap_start = max(self.start_date, other_request.start_date)
        overlap_end = min(self.end_date, other_request.end_date)
        
        if overlap_start > overlap_end:
            return False
        
        for my_slot in self.time_slots:
            for other_slot in other_request.time_slots:
                if self._slots_overlap(my_slot, other_slot):
                    return True
        
        return False