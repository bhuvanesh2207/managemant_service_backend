from django.db import models
from django.conf import settings
from employee.models import Employee


class Salary(models.Model):
    employee = models.ForeignKey(
    Employee,
    on_delete=models.CASCADE,
    related_name='salary_records'
)

    month = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()

    base_salary = models.DecimalField(max_digits=10, decimal_places=2)

    # 🔻 Breakdown
    permission_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    late_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    leave_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    total_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    overtime_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    final_salary = models.DecimalField(max_digits=10, decimal_places=2)

    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL
    )

    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('employee', 'month', 'year')
        db_table = 'employee_salary'

    def __str__(self):
        return f"{self.employee} - {self.month}/{self.year}"