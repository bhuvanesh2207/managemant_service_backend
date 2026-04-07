# attendance/management/commands/sync_zk_attendance.py

import logging
from datetime import datetime, time

from django.core.management.base import BaseCommand
from django.utils import timezone

from attendance.models import AttendanceLog, DailyAttendance, OvertimeRecord
from employee.models import Employee
from attendance.views import calculate_extra_hours, MIN_OT_MINUTES

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# HARDCODED TEST DATA
# ─────────────────────────────────────────────────────────────
TEST_RECORDS = [
    {
        'employee_id': '1',
        'check_in':  time(9, 0),
        'check_out': time(20, 0),
    },
]


class Command(BaseCommand):
    help = 'Sync hardcoded test attendance records and auto-generate OT'

    def handle(self, *args, **options):

        today = timezone.now().date()

        logs_created  = 0
        daily_updated = 0
        skipped       = 0

        # ═════════════════════════════════════════════════════
        # STEP 1 — Save DailyAttendance
        # ═════════════════════════════════════════════════════
        self.stdout.write("\n── STEP 1: Syncing Attendance ──────────────────")

        for entry in TEST_RECORDS:

            try:
                employee = Employee.objects.get(employee_id=entry['employee_id'])
            except Employee.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"❌ Employee '{entry['employee_id']}' not found"
                ))
                skipped += 1
                continue

            check_in  = timezone.make_aware(datetime.combine(today, entry['check_in']))
            check_out = timezone.make_aware(datetime.combine(today, entry['check_out']))

            _, ci_created = AttendanceLog.objects.get_or_create(
                employee=employee,
                timestamp=check_in,
                defaults={'device_user_id': str(employee.employee_id), 'status': 0}
            )
            _, co_created = AttendanceLog.objects.get_or_create(
                employee=employee,
                timestamp=check_out,
                defaults={'device_user_id': str(employee.employee_id), 'status': 1}
            )
            if ci_created: logs_created += 1
            if co_created: logs_created += 1

            total_hours = round(
                (check_out - check_in).total_seconds() / 3600, 2
            )

            if total_hours >= 8:
                status = 'present'
            elif total_hours >= 4:
                status = 'half_day'
            else:
                status = 'absent'

            shift = getattr(getattr(employee, 'shift_assignment', None), 'shift', None)
            extra_hrs, early_mins, late_mins = calculate_extra_hours(
                check_in, check_out, shift, today
            )

            DailyAttendance.objects.update_or_create(
                employee=employee,
                date=today,
                defaults={
                    'check_in':    check_in,
                    'check_out':   check_out,
                    'total_hours': total_hours,
                    'extra_hours': extra_hrs,
                    'status':      status,
                }
            )
            daily_updated += 1

            self.stdout.write(self.style.SUCCESS(
                f"✅ Attendance saved: {employee} | "
                f"total={total_hours}h | extra={extra_hrs}h | status={status}"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"\nSync complete — logs: {logs_created}, "
            f"attendance: {daily_updated}, skipped: {skipped}"
        ))

        # ═════════════════════════════════════════════════════
        # STEP 2 — Auto-generate OvertimeRecords
        # ═════════════════════════════════════════════════════
        self.stdout.write("\n── STEP 2: Auto-generating OT Records ──────────")

        ot_created = 0
        ot_skipped = 0

        for att in DailyAttendance.objects.filter(date=today).select_related(
            'employee', 'employee__shift_assignment__shift'
        ):
            # Skip if OT record already exists
            try:
                att.overtime
                ot_skipped += 1
                self.stdout.write(f"⏭ Skipped {att.employee} — OT record already exists")
                continue
            except OvertimeRecord.DoesNotExist:
                pass

            shift = getattr(getattr(att.employee, 'shift_assignment', None), 'shift', None)
            extra_hrs, early_mins, late_mins = calculate_extra_hours(
                att.check_in, att.check_out, shift, today
            )

            # Fallback to saved extra_hours if no shift
            if not shift:
                extra_hrs  = float(att.extra_hours or 0)
                total_mins = int(extra_hrs * 60)
            else:
                total_mins = early_mins + late_mins

            if total_mins < MIN_OT_MINUTES:
                self.stdout.write(
                    f"⏭ Skipped {att.employee} — "
                    f"only {total_mins} mins OT (min: {MIN_OT_MINUTES})"
                )
                ot_skipped += 1
                continue

            OvertimeRecord.objects.create(
                attendance  = att,
                extra_hours = extra_hrs,
                early_mins  = early_mins,
                late_mins   = late_mins,
            )
            ot_created += 1
            self.stdout.write(self.style.SUCCESS(
                f"✅ OT record created: {att.employee} | "
                f"extra={extra_hrs}h | early={early_mins}m | late={late_mins}m"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"\nOT generation complete — created: {ot_created}, skipped: {ot_skipped}"
        ))

        self.stdout.write(self.style.SUCCESS(
            "\n✅ All done! Attendance synced and OT records generated.\n"
        ))