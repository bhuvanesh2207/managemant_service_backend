from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework import status
from accounts.authentication import JWTAuthenticationFromCookie

from employee.models import Employee
from .models import Salary
from .services import calculate_salary


# ✅ Generate salary (single OR all employees)
@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def generate_salary(request):
    employee_id = request.data.get("employee_id")
    month = request.data.get("month")
    year = request.data.get("year")

    # 🔻 Validation
    if not month or not year:
        return Response(
            {"error": "Month and Year are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        month = int(month)
        year = int(year)
    except ValueError:
        return Response(
            {"error": "Month and Year must be integers"},
            status=status.HTTP_400_BAD_REQUEST
        )

    employees = Employee.objects.filter(status='active')

    if employee_id:
        employees = employees.filter(id=employee_id)
        if not employees.exists():
            return Response(
                {"error": "Employee not found"},
                status=status.HTTP_404_NOT_FOUND
            )

    results = []

    for emp in employees:
        data = calculate_salary(emp, month, year)

        Salary.objects.update_or_create(
            employee=emp,
            month=month,
            year=year,
            defaults={**data, "generated_by": request.user}
        )

        results.append({
            "employee": emp.full_name,
            "employee_id": emp.id,
            "final_salary": data["final_salary"]
        })

    return Response({
        "message": "Salary generated successfully",
        "count": len(results),
        "data": results
    }, status=status.HTTP_200_OK)


# ✅ Salary list API
@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def salary_list(request):
    qs = Salary.objects.select_related('employee').order_by('-year', '-month')

    employee = request.query_params.get('employee')
    month = request.query_params.get('month')
    year = request.query_params.get('year')

    # 🔻 Filters
    try:
        if employee:
            qs = qs.filter(employee__id=int(employee))
        if month:
            qs = qs.filter(month=int(month))
        if year:
            qs = qs.filter(year=int(year))
    except ValueError:
        return Response(
            {"error": "Invalid query parameters"},
            status=status.HTTP_400_BAD_REQUEST
        )

    data = [
        {
            "id": s.id,
            "employee": s.employee.full_name,
            "employee_id": s.employee.id,
            "month": s.month,
            "year": s.year,
            "base_salary": s.base_salary,
            "final_salary": s.final_salary,
            "total_deduction": s.total_deduction,
            "overtime_amount": s.overtime_amount,
            "generated_at": s.generated_at,
        }
        for s in qs
    ]

    return Response({
        "success": True,
        "count": qs.count(),
        "data": data
    }, status=status.HTTP_200_OK)