import os
import logging

from django.shortcuts import get_object_or_404
from django.http import FileResponse, Http404
from django.conf import settings

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes, action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from accounts.authentication import JWTAuthenticationFromCookie

from .models import Employee, WorkShift, EmployeeShift
from .serializers import (
    EmployeeSerializer,
    EmployeeCreateSerializer,
    EmployeeUpdateSerializer,
    WorkShiftSerializer,
    EmployeeShiftSerializer,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────
# 🔹 CREATE EMPLOYEE
# ─────────────────────────────────────────
@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def add_employee(request):
    serializer = EmployeeCreateSerializer(data=request.data)
    if serializer.is_valid():
        employee = serializer.save()
        logger.info(f"Employee created: {employee.full_name} by {request.user}")
        return Response(
            {"success": True, "employee_id": employee.id},
            status=status.HTTP_201_CREATED,
        )
    return Response(
        {"success": False, "errors": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


# ─────────────────────────────────────────
# 🔹 LIST EMPLOYEES
# ─────────────────────────────────────────
@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def list_employees(request):
    if request.user.is_superuser:
        employees = Employee.objects.all().order_by('-id')
    else:
        try:
            employees = Employee.objects.filter(pk=request.user.employee_profile.pk)
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee account not linked. Contact administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

    serializer = EmployeeSerializer(employees, many=True)
    return Response(
        {"success": True, "employees": serializer.data},
        status=status.HTTP_200_OK,
    )


# ─────────────────────────────────────────
# 🔹 GET SINGLE EMPLOYEE
# ─────────────────────────────────────────
@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def get_employee(request, employee_id):
    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        employee = get_object_or_404(Employee, pk=employee_id)

    if not request.user.is_superuser:
        try:
            if employee != request.user.employee_profile:
                return Response(
                    {"detail": "Employee not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee account not linked. Contact administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

    serializer = EmployeeSerializer(employee)
    return Response(
        {"success": True, "employee": serializer.data},
        status=status.HTTP_200_OK,
    )


# ─────────────────────────────────────────
# 🔹 UPDATE EMPLOYEE
# ─────────────────────────────────────────
@api_view(['PATCH'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def update_employee(request, employee_id):
    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        employee = get_object_or_404(Employee, pk=employee_id)

    if not request.user.is_superuser:
        try:
            if employee != request.user.employee_profile:
                return Response(
                    {"detail": "Employee not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee account not linked. Contact administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

    serializer = EmployeeUpdateSerializer(employee, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        logger.info(f"Employee updated: {employee.full_name} by {request.user}")
        return Response(
            {"success": True, "message": "Employee updated successfully"},
            status=status.HTTP_200_OK,
        )
    return Response(
        {"success": False, "errors": serializer.errors},
        status=status.HTTP_400_BAD_REQUEST,
    )


# ─────────────────────────────────────────
# 🔹 DELETE EMPLOYEE (SOFT DELETE)
# ─────────────────────────────────────────
@api_view(['DELETE'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def delete_employee(request, employee_id):
    try:
        employee = Employee.objects.get(employee_id=employee_id)
    except Employee.DoesNotExist:
        employee = get_object_or_404(Employee, pk=employee_id)

    if not request.user.is_superuser:
        try:
            if employee != request.user.employee_profile:
                return Response(
                    {"detail": "Employee not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee account not linked. Contact administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

    employee.status = 'inactive'
    employee.save()
    logger.info(f"Employee deactivated: {employee.full_name} by {request.user}")
    return Response(
        {"success": True, "message": "Employee deactivated successfully"},
        status=status.HTTP_200_OK,
    )


# ─────────────────────────────────────────
# 🔹 WORK SHIFT VIEWSET
# ─────────────────────────────────────────
class WorkShiftViewSet(ModelViewSet):
    queryset = WorkShift.objects.all()
    serializer_class = WorkShiftSerializer
    authentication_classes = [JWTAuthenticationFromCookie]
    permission_classes = [IsAuthenticated]


# ─────────────────────────────────────────
# 🔹 EMPLOYEE SHIFT VIEWSET
# ─────────────────────────────────────────
class EmployeeShiftViewSet(ModelViewSet):
    queryset = EmployeeShift.objects.all()
    serializer_class = EmployeeShiftSerializer
    authentication_classes = [JWTAuthenticationFromCookie]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = EmployeeShift.objects.all()
        employee_id = self.request.query_params.get('employee_id')
        if not self.request.user.is_superuser:
            try:
                queryset = queryset.filter(employee=self.request.user.employee_profile)
            except Employee.DoesNotExist:
                queryset = queryset.none()
        elif employee_id:
            queryset = queryset.filter(employee__employee_id=employee_id)
        return queryset

    # ─────────────────────────────────────────
    # 🔹 BULK ASSIGN — updates if already assigned
    # ─────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='assign_bulk')
    def assign_bulk(self, request):
        shift_id     = request.data.get("shift")
        start_date   = request.data.get("start_date")
        employee_ids = request.data.get("employee_ids", [])

        if not shift_id or not start_date or not employee_ids:
            return Response(
                {"success": False, "message": "Missing required fields: shift, start_date, employee_ids"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        created_list, updated_list, not_found = [], [], []

        for emp_id in employee_ids:
            try:
                employee = Employee.objects.get(employee_id=emp_id)

                # ✅ update_or_create: replaces old shift instead of adding a new row
                obj, created = EmployeeShift.objects.update_or_create(
                    employee=employee,
                    defaults={
                        "shift_id": shift_id,
                        "start_date": start_date,
                    },
                )

                if created:
                    created_list.append(obj.id)
                else:
                    updated_list.append(obj.id)

            except Employee.DoesNotExist:
                not_found.append(str(emp_id))
                logger.warning(f"Employee '{emp_id}' not found during bulk shift assign.")

        if not_found:
            return Response(
                {
                    "success": False,
                    "message": f"Some employees were not found: {', '.join(not_found)}",
                    "created_count": len(created_list),
                    "updated_count": len(updated_list),
                },
                status=status.HTTP_207_MULTI_STATUS,
            )

        return Response(
            {
                "success": True,
                "created_count": len(created_list),
                "updated_count": len(updated_list),
                "message": f"Done — {len(created_list)} assigned, {len(updated_list)} updated.",
            },
            status=status.HTTP_200_OK,
        )

    # ─────────────────────────────────────────
    # 🔹 SINGLE ASSIGN — updates if already assigned
    # ─────────────────────────────────────────
    @action(detail=False, methods=['post'], url_path='assign')
    def assign(self, request):
        emp_id     = request.data.get("employee_id")
        shift_id   = request.data.get("shift")
        start_date = request.data.get("start_date")

        if not emp_id or not shift_id or not start_date:
            return Response(
                {"success": False, "message": "Missing required fields: employee_id, shift, start_date"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            employee = Employee.objects.get(employee_id=emp_id)
        except Employee.DoesNotExist:
            return Response(
                {"success": False, "message": f"Employee '{emp_id}' not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        shift = get_object_or_404(WorkShift, pk=shift_id)

        # ✅ update_or_create: replaces old shift instead of adding a new row
        obj, created = EmployeeShift.objects.update_or_create(
            employee=employee,
            defaults={
                "shift": shift,
                "start_date": start_date,
            },
        )

        logger.info(
            f"Shift '{shift.name}' {'assigned to' if created else 'updated for'} "
            f"employee '{emp_id}' by {request.user}"
        )
        return Response(
            {
                "success": True,
                "message": f"Shift '{shift.name}' {'assigned to' if created else 'updated for'} {employee.full_name} successfully.",
                "assignment_id": obj.id,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


# ─────────────────────────────────────────
# 🔹 SECURE MEDIA FILE SERVING
# ─────────────────────────────────────────
@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def serve_employee_file(request, file_path):
    safe_path = os.path.normpath(file_path).lstrip('/')
    full_path = os.path.join(settings.MEDIA_ROOT, safe_path)

    if not full_path.startswith(settings.MEDIA_ROOT):
        raise Http404("Invalid path")
    if not os.path.exists(full_path):
        raise Http404("File not found")

    return FileResponse(open(full_path, 'rb'))