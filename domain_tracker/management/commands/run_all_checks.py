from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = "Run all system checks"

    def handle(self, *args, **kwargs):
        call_command('check_expiry')

        self.stdout.write("\n All checks completed")