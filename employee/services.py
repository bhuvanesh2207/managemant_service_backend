import logging
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.db import transaction
from django.utils.crypto import get_random_string
from django.conf import settings

from .models import Employee

logger = logging.getLogger(__name__)


def send_welcome_email(employee, temp_password=None):
    """Send welcome email to employee."""
    try:
        if not settings.EMAIL_HOST_USER or not settings.EMAIL_HOST_PASSWORD:
            raise ValueError("EMAIL_HOST_USER or EMAIL_HOST_PASSWORD not configured.")

        if temp_password:
            message = (
                f"Hi {employee.full_name},\n\n"
                f"Your employee account has been created.\n\n"
                f"Login Email:    {employee.email}\n"
                f"Temp Password:  {temp_password}\n\n"
                f"Please log in and change your password immediately.\n\n"
                f"Regards,\nHR Team"
            )
        else:
            message = (
                f"Hi {employee.full_name},\n\n"
                f"Your employee record has been created in our system.\n"
                f"Login Email: {employee.email}\n\n"
                f"If you do not have a password yet, please ask the administrator to reset your password.\n\n"
                f"Regards,\nHR Team"
            )

        send_mail(
            subject="Your Employee Login Credentials",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER,
            recipient_list=[employee.email],
            fail_silently=False,
        )
        employee.email_sent = True
        employee.save(update_fields=['email_sent'])
        logger.info(f"Welcome email sent to {employee.email}")
    except Exception as e:
        logger.error(f"Failed to send welcome email to '{employee.email}': {e}")


def create_employee_with_user(validated_data):
    user = validated_data.pop('user', None)
    temp_password = None

    email = validated_data.get('email')

    if user is None:
        try:
            existing_user = User.objects.get(email=email)
            if not existing_user.is_superuser and not hasattr(existing_user, 'employee_profile'):
                user = existing_user
                # Always generate a fresh temp password for existing users too
                temp_password = get_random_string(length=12)
                existing_user.set_password(temp_password)
                existing_user.save(update_fields=['password'])

        except User.DoesNotExist:
            temp_password = get_random_string(length=12)

            base_username = email.split('@')[0]
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1

            user = User.objects.create_user(
                username=username,
                email=email,
                password=temp_password,
                is_active=True,
            )

    if user is not None:
        validated_data['user'] = user

    with transaction.atomic():
        employee = Employee.objects.create(**validated_data)
        if temp_password:
            employee.is_temp_password = True
            employee.save(update_fields=['is_temp_password'])

    if employee.email:
        # ✅ FIX: Capture temp_password by value using a default argument
        transaction.on_commit(
            lambda emp=employee, pwd=temp_password: send_welcome_email(emp, pwd)
        )

    return employee

