from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, date, timedelta, time
from decimal import Decimal
from unittest.mock import patch

from employee.models import Employee, WorkShift, EmployeeShift
from attendance.models import DailyAttendance, EmployeePermission, Leave
from salary.services import calculate_salary


class TestSalaryCalculation(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Shared fixtures
        cls.user = User.objects.create(username='testuser')
        cls.employee = Employee.objects.create(
            user=cls.user,
            employee_id='EMP001',
            full_name='Test Employee',
            salary=Decimal('30000.00'),
            status='active'
        )
        cls.shift = WorkShift.objects.create(
            name='General',
            start_time=time(9, 0),
            end_time=time(17, 0),
            break_hours=Decimal('1.00'),
            working_hours=Decimal('8.00')
        )
        cls.employeeshift = EmployeeShift.objects.create(
            employee=cls.employee,
            shift=cls.shift,
            start_date=date(2024, 10, 1)
        )

    def test_perfect_attendance(self):
        # 30 days perfect, no data affecting deduct
        month, year = 10, 2024
        result = calculate_salary(self.employee, month, year)
        self.assertEqual(result['base_salary'], Decimal('30000.00'))
        self.assertEqual(result['permission_deduction'], Decimal('0.00'))
        self.assertEqual(result['late_deduction'], Decimal('0.00'))
        self.assertEqual(result['leave_deduction'], Decimal('0.00'))
        self.assertEqual(result['overtime_amount'], Decimal('0.00'))
        self.assertEqual(result['final_salary'], Decimal('30000.00'))

    def test_late_deduction_full_day(self):
        # 3 days late 4h each =12h total >=4 -> full day deduct 1000
        month, year = 10, 2024
        test_date = date(2024, 10, 1)
        for i in range(3):
            att_date = test_date + timedelta(days=i)
            shift_start = datetime.combine(att_date, time(9,0))
            late_in = shift_start + timedelta(hours=4)
            DailyAttendance.objects.create(
                employee=self.employee,
                date=att_date,
                check_in=late_in,
                status='present'
            )
        result = calculate_salary(self.employee, month, year)
        self.assertEqual(result['late_deduction'], Decimal('1000.00'))
        self.assertEqual(result['final_salary'], Decimal('29000.00'))

    def test_late_deduction_half_day(self):
        # Total late 2.5h (2 days *1.25? Wait, adjust to test half threshold
        # To test >=2 <4: 2 days 1.5h late =3h total
        month, year = 10, 2024
        test_date = date(2024, 10, 1)
        for i in range(2):
            att_date = test_date + timedelta(days=i)
            shift_start = datetime.combine(att_date, time(9,0))
            late_in = shift_start + timedelta(hours=1.5)
            DailyAttendance.objects.create(
                employee=self.employee,
                date=att_date,
                check_in=late_in,
                status='present'
            )
        result = calculate_salary(self.employee, month, year)
        self.assertEqual(result['late_deduction'], Decimal('500.00'))
        self.assertEqual(result['final_salary'], Decimal('29500.00'))

    def test_early_offset_late(self):
        month, year = 10, 2024
        test_date = date(2024, 10, 1)
        shift_start = datetime.combine(test_date, time(9,0))
        # Day 1: 2h early + 0 late
        early_in = shift_start - timedelta(hours=2)
        DailyAttendance.objects.create(employee=self.employee, date=test_date, check_in=early_in, status='present')
        # Day 2: 3h late
        day2 = test_date + timedelta(days=1)
        day2_start = datetime.combine(day2, time(9,0))
        late_in = day2_start + timedelta(hours=3)
        DailyAttendance.objects.create(employee=self.employee, date=day2, check_in=late_in, status='present')
        result = calculate_salary(self.employee, month, year)
        self.assertEqual(result['late_deduction'], Decimal('0.00'))
        self.assertEqual(result['final_salary'], Decimal('30000.00'))

    def test_permission_deduction(self):
        month, year = 10, 2024
        test_date = date(2024, 10, 1)
        test_datetime = timezone.now()
        EmployeePermission.objects.create(
            employee=self.employee,
            permission_type='MID_DAY',
            request_type='EMERGENCY',
            reason='Test reason',
            expected_end_time=test_datetime,
            date=test_date,
            duration=Decimal('3.0'),
            status='COMPLETED'
        )
        result = calculate_salary(self.employee, month, year)
        self.assertEqual(result['permission_deduction'], Decimal('125.00'))
        self.assertEqual(result['final_salary'], Decimal('29875.00'))

    def test_leave_deduction(self):
        month, year = 10, 2024
        Leave.objects.create(
            employee=self.employee,
            start_date=date(2024,10,1),
            end_date=date(2024,10,2),
            status='APPROVED',
            leave_type='CASUAL'
        )
        result = calculate_salary(self.employee, month, year)
        self.assertEqual(result['leave_deduction'], Decimal('1000.00'))
        self.assertEqual(result['final_salary'], Decimal('29000.00'))

    def test_overtime(self):
        month, year = 10, 2024
        test_date = date(2024, 10, 1)
        DailyAttendance.objects.create(
            employee=self.employee,
            date=test_date,
            extra_hours=Decimal('10.0'),
            status='present'
        )
        result = calculate_salary(self.employee, month, year)
        self.assertEqual(result['overtime_amount'], Decimal('1250.00')) 
        self.assertEqual(result['final_salary'], Decimal('31250.00'))

    def test_all_deductions_and_overtime(self):
        month, year = 10, 2024
        test_date = date(2024,10,1)
        # Late full
        for i in range(3):
            att_date = test_date + timedelta(days=i)
            shift_start = timezone.make_aware(datetime.combine(att_date, time(9,0)))
            late_in = shift_start + timedelta(hours=4)
            DailyAttendance.objects.create(
                employee=self.employee,
                date=att_date,
                check_in=late_in,
                status='present'
            )
        test_datetime = timezone.now()
        EmployeePermission.objects.create(
            employee=self.employee,
            permission_type='MID_DAY',
            request_type='EMERGENCY',
            reason='Test reason',
            expected_end_time=test_datetime,
            date=test_date,
            duration=Decimal('3.00'),
            status='COMPLETED'
        )
        Leave.objects.create(employee=self.employee, start_date=date(2024,10,10), end_date=date(2024,10,11), status='APPROVED', leave_type='CASUAL')
        DailyAttendance.objects.create(employee=self.employee, date=test_date+timedelta(days=5), extra_hours=Decimal('10'), status='present')
        result = calculate_salary(self.employee, month, year)
        self.assertEqual(result['total_deduction'], Decimal('2125.00'))
        self.assertEqual(result['final_salary'], Decimal('29125.00'))

    def test_no_shift_assignment(self):
        # Delete shift
        self.employeeshift.delete()
        month, year = 10, 2024
        # Late att but no shift -> no late deduct
        test_date = date(2024,10,1)
        DailyAttendance.objects.create(employee=self.employee, date=test_date, status='present')
        result = calculate_salary(self.employee, month, year)
        self.assertEqual(result['late_deduction'], Decimal('0.00'))

    def test_no_salary(self):
        self.employee.salary = None
        self.employee.save()
        result = calculate_salary(self.employee, 10, 2024)
        self.assertEqual(result['base_salary'], Decimal('0.00'))
        self.assertLessEqual(result['final_salary'], Decimal('0.00'))

    def test_no_data(self):
        # Empty month
        result = calculate_salary(self.employee, 11, 2024)  # No data
        self.assertEqual(result['total_deduction'], Decimal('0.00'))
        self.assertEqual(result['overtime_amount'], Decimal('0.00'))
        self.assertEqual(result['final_salary'], Decimal('30000.00'))

