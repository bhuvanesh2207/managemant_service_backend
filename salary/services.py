from datetime import datetime
from decimal import Decimal
from django.db.models import Sum
from attendance.models import DailyAttendance, EmployeePermission, Leave


def calculate_salary(employee, month, year):
    # 🔹 Fetch data
    attendances = DailyAttendance.objects.filter(
        employee=employee,
        date__month=month,
        date__year=year
    )

    permissions = EmployeePermission.objects.filter(
        employee=employee,
        date__month=month,
        date__year=year,
        status='COMPLETED'
    )

    leaves = Leave.objects.filter(
        employee=employee,
        start_date__month=month,
        start_date__year=year,
        status='APPROVED',
        leave_type='CASUAL'
    )

    # 🔹 Salary base
    base_salary = Decimal(employee.salary or 0)
    per_day_salary = base_salary / Decimal(30)
    per_hour_salary = per_day_salary / Decimal(8)

    # 🔹 Initialize trackers
    total_extra_hours = Decimal(0)
    total_late_hours = Decimal(0)
    early_extra_hours = Decimal(0)

    permission_deduction = Decimal(0)
    late_deduction = Decimal(0)
    leave_deduction = Decimal(0)

    # 🔹 Attendance processing
    for att in attendances:
        if att.extra_hours:
            total_extra_hours += Decimal(att.extra_hours)

        if not hasattr(employee, "shift_assignment"):
            continue

        shift = employee.shift_assignment.shift
        shift_start = datetime.combine(att.date, shift.start_time)

        if att.check_in:
            diff = Decimal((att.check_in - shift_start).total_seconds() / 3600)

            if diff > 0:
                total_late_hours += diff
            else:
                early_extra_hours += abs(diff)

    # 🔹 Adjust late with early extra
    adjusted_late = max(Decimal(0), total_late_hours - early_extra_hours)

    # 🔻 Late deduction (FIXED ✅)
    if adjusted_late >= 4:
        late_deduction = per_day_salary
    elif adjusted_late >= 2:
        late_deduction = per_day_salary / Decimal(2)

    # 🔻 Permission deduction
    total_permission = permissions.aggregate(
        total=Sum('duration')
    )['total'] or 0

    total_permission = Decimal(total_permission)

    if total_permission > 2:
        extra_hours = total_permission - Decimal(2)
        permission_deduction = extra_hours * per_hour_salary

    # 🔻 Leave deduction (multi-day safe)
    total_leave_days = 0
    for leave in leaves:
        total_leave_days += (leave.end_date - leave.start_date).days + 1

    if total_leave_days > 1:
        leave_deduction = Decimal(total_leave_days - 1) * per_day_salary

    # 🔹 Overtime
    overtime_amount = total_extra_hours * per_hour_salary

    # 🔹 Final calculations
    total_deduction = permission_deduction + late_deduction + leave_deduction
    final_salary = base_salary - total_deduction + overtime_amount

    return {
        "base_salary": round(base_salary, 2),
        "permission_deduction": round(permission_deduction, 2),
        "late_deduction": round(late_deduction, 2),
        "leave_deduction": round(leave_deduction, 2),
        "total_deduction": round(total_deduction, 2),
        "overtime_amount": round(overtime_amount, 2),
        "final_salary": round(final_salary, 2),
    }