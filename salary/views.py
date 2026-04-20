from rest_framework.decorators import api_view
from rest_framework.response import Response
from employee.models import Employee
from .models import Salary
from .services import calculate_salary


@api_view(['POST'])
def generate_salary(request):
    month = int(request.data.get("month"))
    year = int(request.data.get("year"))

    results = []

    employees = Employee.objects.filter(status='active')

    for emp in employees:
        data = calculate_salary(emp, month, year)

        salary_obj, _ = Salary.objects.update_or_create(
            employee=emp,
            month=month,
            year=year,
            defaults={
                **data,
                "generated_by": request.user
            }
        )

        results.append({
            "employee": emp.full_name,
            "final_salary": data["final_salary"]
        })

    return Response({
        "message": "Salary generated successfully",
        "data": results
    })