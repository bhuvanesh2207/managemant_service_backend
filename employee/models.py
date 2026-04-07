from django.contrib.auth.models import User
from django.db import models


class Employee(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee_profile'
    )

    # -------------------------
    # 🔹 Personal Info
    # -------------------------
    employee_id = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=255)

    DESIGNATION_CHOICES = [
        ('software_developer', 'Software Developer'),
        ('graphic_designer', 'Graphic Designer'),
        ('web_designer', 'Web Designer'),
        ('ui_ux_designer', 'UI/UX Designer'),
        ('business_analyst', 'Business Analyst'),
    ]
    designation = models.CharField(max_length=50, choices=DESIGNATION_CHOICES, blank=True, null=True)

    dob = models.DateField(blank=True, null=True)
    date_of_joining = models.DateField(blank=True, null=True)

    current_address = models.TextField(blank=True, null=True)
    permanent_address = models.TextField(blank=True, null=True)

    primary_contact_no = models.CharField(max_length=15, blank=True, null=True)
    alt_contact_no = models.CharField(max_length=15, blank=True, null=True)

    email = models.EmailField(unique=True)

    salary = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    # -------------------------
    # 🔹 Document Fields (uploads)
    # -------------------------
    aadhaar_card = models.FileField(upload_to='employee_documents/aadhaar/', blank=True, null=True)
    pan = models.FileField(upload_to='employee_documents/pan/', blank=True, null=True)
    photo = models.ImageField(upload_to='employee_photos/', blank=True, null=True)

    # -------------------------
    # 🔹 Emergency & Medical
    # -------------------------
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'),
        ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'),
        ('O+', 'O+'), ('O-', 'O-'),
    ]
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, default="")

    emergency_contact_person = models.CharField(max_length=255, default="")
    emergency_contact_no = models.CharField(max_length=15, default="")
    emergency_relationship = models.CharField(max_length=100, default="")

    medical_conditions = models.TextField(blank=True, null=True)

    # -------------------------
    # 🔹 Bank / Account Details
    # -------------------------
    bank_name = models.CharField(max_length=255, blank=True, null=True)
    account_holder_name = models.CharField(max_length=255, blank=True, null=True)
    account_number = models.CharField(max_length=30, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    bank_branch = models.CharField(max_length=255, blank=True, null=True)

    ACCOUNT_TYPE_CHOICES = [
        ('savings', 'Savings'),
        ('current', 'Current'),
    ]
    account_type = models.CharField(
        max_length=10, choices=ACCOUNT_TYPE_CHOICES, blank=True, null=True
    )

    # -------------------------
    # 🔹 Status
    # -------------------------
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    # -------------------------
    # 🔹 Password & Email Status
    # -------------------------
    is_temp_password = models.BooleanField(default=False)
    email_sent = models.BooleanField(default=False)

    # -------------------------
    # 🔹 Meta Info
    # -------------------------
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    device_user_id = models.CharField(max_length=50, blank=True, null=True, unique=True)

    def __str__(self):
        return self.full_name


class WorkShift(models.Model):
    name = models.CharField(max_length=100)
    start_time = models.TimeField()
    end_time = models.TimeField()
    break_hours = models.DecimalField(max_digits=4, decimal_places=2, default=1)
    working_hours = models.DecimalField(max_digits=4, decimal_places=2)

    def __str__(self):
        return self.name


class EmployeeShift(models.Model):
    employee = models.OneToOneField(Employee, on_delete=models.CASCADE, related_name='shift_assignment')
    shift = models.ForeignKey(WorkShift, on_delete=models.CASCADE)
    start_date = models.DateField()

    def __str__(self):
        return f"{self.employee} - {self.shift}"