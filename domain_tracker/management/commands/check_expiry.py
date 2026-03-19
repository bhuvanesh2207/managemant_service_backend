from django.core.management.base import BaseCommand
from django.conf import settings
from datetime import date
from domain_tracker.models import Domain
from domain_tracker.utils import send_combined_expiry_mail


class Command(BaseCommand):
    help = "Check expiry dates and send ONE combined email per domain"
    def handle(self, *args, **kwargs):
        domains = Domain.objects.all()

        for d in domains:
            self.process_domain(d)
    def process_domain(self, d):
        today = date.today()

        services = []

        def check(service_name, name, expiry_date):
            if not name or not expiry_date:
                return

            days_left = (expiry_date - today).days

            if days_left == 30 or (0 < days_left <= 7) or days_left <= 0:
                services.append({
                    "type": service_name,
                    "name": name,
                    "expiry_date": expiry_date,
                    "days_left": days_left
                })
        check("Domain", d.domain_name, d.expiry_date)
        check("SSH", d.ssh_name, d.ssh_expiry_date)
        check("Hosting", d.hosting_name, d.hosting_expiry_date)

        if services:
            subject = f"Expiry Alert - {d.domain_name}"
            recipient = settings.EMAIL_HOST_USER

            send_combined_expiry_mail(subject, services, recipient)