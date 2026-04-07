from django.core.mail import EmailMessage
from django.core.mail.backends.smtp import EmailBackend
from .models import EmailConfig


def get_email_backend():
    """Load SMTP settings from DB and return a live backend instance."""
    try:
        config = EmailConfig.objects.latest('updated_at')
    except EmailConfig.DoesNotExist:
        raise RuntimeError("No email configuration found. Please set it up from the admin panel.")

    return EmailBackend(
        host=config.email_host,
        port=config.email_port,
        username=config.email_host_user,
        password=config.email_host_password,
        use_tls=config.email_use_tls,
        fail_silently=False,
    )


def send_dynamic_mail(subject, message, recipient_list, from_email=None):
    """Send email using DB-stored credentials."""
    config = EmailConfig.objects.latest('updated_at')
    backend = get_email_backend()

    email = EmailMessage(
        subject=subject,
        body=message,
        from_email=from_email or config.email_host_user,
        to=recipient_list,
        connection=backend,
    )
    email.send()