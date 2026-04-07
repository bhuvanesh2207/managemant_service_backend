from django.db import models
from employee.models import Employee


class Holiday(models.Model):
    DAY_TYPE_CHOICES = [
        ('HOLIDAY', 'Holiday'),
        ('FESTIVAL', 'Festival'),
    ]

    name = models.CharField(max_length=255)
    date = models.DateField()
    day_type = models.CharField(max_length=10, choices=DAY_TYPE_CHOICES)
    group_id = models.CharField(max_length=100, blank=True, null=True)
    max_allowed_leaves = models.PositiveIntegerField(blank=True, null=True)

    class Meta:
        ordering = ['date']
        db_table = 'attendance_holiday'

    def __str__(self):
        return f"{self.name} ({self.date}) — {self.day_type}"


class AttendanceLog(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    device_user_id = models.CharField(max_length=50)
    timestamp = models.DateTimeField()
    status = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee} - {self.timestamp}"


class DailyAttendance(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()

    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)

    total_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    extra_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    ot_eligible = models.BooleanField(default=False)

    STATUS = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('half_day', 'Half Day'),
    ]
    status = models.CharField(max_length=20, choices=STATUS)

    class Meta:
        unique_together = ('employee', 'date')

class Permission(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    date = models.DateField()

    start_time = models.TimeField()
    end_time = models.TimeField()

    duration = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)

    reason = models.TextField()

    STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS, default='pending')

    created_at = models.DateTimeField(auto_now_add=True)
    
from django.conf import settings

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
        settings.AUTH_USER_MODEL,        # ← was "accounts.User"
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="ot_reviews"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-attendance__date"]

    def __str__(self):
        return f"{self.attendance.employee} – {self.extra_hours}h ({self.status})"