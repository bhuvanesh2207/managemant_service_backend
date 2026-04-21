# attendance/management/commands/sync_zk_attendance.py

import logging
import random
from datetime import datetime, time
from calendar import monthrange

from django.core.management.base import BaseCommand
from django.utils import timezone

from attendance.models import AttendanceLog, DailyAttendance, OvertimeRecord
from employee.models import Employee
from attendance.views import calculate_extra_hours, MIN_OT_MINUTES

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate attendance for a full month + OT"

    def add_arguments(self, parser):
        parser.add_argument('--employee_id', type=str, help='Employee ID (optional)')
        parser.add_argument('--month', type=int, required=True)
        parser.add_argument('--year', type=int, required=True)

    def handle(self, *args, **options):

        employee_id = options.get('employee_id')
        month = options['month']
        year = options['year']

        # 🔹 Select employees
        employees = Employee.objects.filter(status='active')

        if employee_id:
            employees = employees.filter(employee_id=employee_id)

        if not employees.exists():
            self.stdout.write(self.style.ERROR("❌ No employees found"))
            return

        total_days = monthrange(year, month)[1]

        logs_created = 0
        attendance_created = 0
        ot_created = 0

        self.stdout.write(f"\n🚀 Generating attendance for {month}/{year}")

        for employee in employees:

            self.stdout.write(f"\n👤 Processing: {employee}")

            for day in range(1, total_days + 1):

                date = datetime(year, month, day).date()

                # 🔻 Skip Sundays
                if date.weekday() == 6:
                    continue

                # 🔹 Slight randomization (realistic)
                check_in_time = time(9, random.randint(0, 30))
                check_out_time = time(18, random.randint(0, 45))

                check_in = timezone.make_aware(datetime.combine(date, check_in_time))
                check_out = timezone.make_aware(datetime.combine(date, check_out_time))

                # 🔹 Logs
                _, ci_created = AttendanceLog.objects.get_or_create(
                    employee=employee,
                    timestamp=check_in,
                    defaults={
                        'device_user_id': str(employee.employee_id),
                        'status': 0
                    }
                )

                _, co_created = AttendanceLog.objects.get_or_create(
                    employee=employee,
                    timestamp=check_out,
                    defaults={
                        'device_user_id': str(employee.employee_id),
                        'status': 1
                    }
                )

                if ci_created:
                    logs_created += 1
                if co_created:
                    logs_created += 1

                # 🔹 Work hours
                total_hours = round(
                    (check_out - check_in).total_seconds() / 3600, 2
                )

                if total_hours >= 8:
                    status = 'present'
                elif total_hours >= 4:
                    status = 'half_day'
                else:
                    status = 'absent'

                shift = getattr(
                    getattr(employee, 'shift_assignment', None),
                    'shift',
                    None
                )

                extra_hrs, early_mins, late_mins = calculate_extra_hours(
                    check_in, check_out, shift, date
                )

                # 🔹 Daily Attendance
                att, created = DailyAttendance.objects.update_or_create(
                    employee=employee,
                    date=date,
                    defaults={
                        'check_in': check_in,
                        'check_out': check_out,
                        'total_hours': total_hours,
                        'extra_hours': extra_hrs,
                        'status': status,
                    }
                )

                if created:
                    attendance_created += 1

                # 🔹 OT Generation
                if hasattr(att, 'overtime'):
                    continue

                if shift:
                    total_mins = early_mins + late_mins
                else:
                    total_mins = int((extra_hrs or 0) * 60)

                if total_mins < MIN_OT_MINUTES:
                    continue

                OvertimeRecord.objects.create(
                    attendance=att,
                    extra_hours=extra_hrs,
                    early_mins=early_mins,
                    late_mins=late_mins,
                )

                ot_created += 1

                self.stdout.write(
                    f"✅ {date} | {status} | {total_hours}h | OT: {extra_hrs}h"
                )

        self.stdout.write(self.style.SUCCESS("\n🎉 DONE"))
        self.stdout.write(self.style.SUCCESS(
            f"Logs: {logs_created}, Attendance: {attendance_created}, OT: {ot_created}"
        ))