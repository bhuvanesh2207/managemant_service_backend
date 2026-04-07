from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class PasswordResetOTP(models.Model):
    """
    Stores one active OTP per admin email for the forgot-password flow.
    On every new send request the existing record is overwritten (update_or_create).
    The record is hard-deleted once the password is successfully reset.
    """
    email      = models.EmailField(unique=True)   # one active OTP per email
    otp        = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_verified = models.BooleanField(default=False)  # flipped to True after verify step

    class Meta:
        verbose_name     = "Password Reset OTP"
        verbose_name_plural = "Password Reset OTPs"

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.email} — expires {self.expires_at} | verified={self.is_verified}"    
    
class EmailConfig(models.Model):
    email_host      = models.CharField(max_length=255, default='smtp.gmail.com')
    email_port      = models.IntegerField(default=587)
    email_use_tls   = models.BooleanField(default=True)
    email_host_user = models.EmailField()
    email_host_password = models.CharField(max_length=255)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Email Configuration"

    def __str__(self):
        return f"Email Config ({self.email_host_user})"