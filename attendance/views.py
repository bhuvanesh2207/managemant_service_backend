import logging
from datetime import datetime, timedelta

from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from accounts.authentication import JWTAuthenticationFromCookie
from .models import Holiday, AttendanceLog, DailyAttendance, Permission, OvertimeRecord
from employee.models import Employee
from .serializers import (
    HolidaySerializer,
    HolidayCreateSerializer,
    AttendanceLogSerializer,
    DailyAttendanceSerializer,
    PermissionSerializer,
    OvertimeRecordSerializer,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# POST /api/attendance/holiday/add/
# ─────────────────────────────────────────────────────────────
@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def add_holiday(request):
    serializer = HolidayCreateSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = serializer.save()

    if isinstance(result, list):
        logger.info(
            f"Festival created: '{result[0].name}' group='{result[0].group_id}' "
            f"({len(result)} dates) by {request.user}"
        )
        return Response(
            {
                "success": True,
                "message": f"Festival added successfully with {len(result)} date(s).",
                "group_id": result[0].group_id,
                "holiday_ids": [h.id for h in result],
                "dates": [str(h.date) for h in result],
            },
            status=status.HTTP_201_CREATED,
        )
    else:
        logger.info(f"Holiday created: '{result.name}' on {result.date} by {request.user}")
        return Response(
            {
                "success": True,
                "message": "Holiday added successfully.",
                "holiday_id": result.id,
            },
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────
# GET /api/attendance/calendar/
# ─────────────────────────────────────────────────────────────
@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def get_calendar(request):
    queryset = Holiday.objects.all()

    year  = request.query_params.get('year')
    month = request.query_params.get('month')

    if year:
        queryset = queryset.filter(date__year=int(year))
    if month:
        queryset = queryset.filter(date__month=int(month))

    serializer = HolidaySerializer(queryset, many=True)
    return Response(
        {"success": True, "calendar": serializer.data},
        status=status.HTTP_200_OK,
    )


# ─────────────────────────────────────────────────────────────
# GET /api/attendance/group/<group_id>/
# ─────────────────────────────────────────────────────────────
@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def get_group(request, group_id):
    holidays = Holiday.objects.filter(group_id=group_id.upper())

    if not holidays.exists():
        return Response(
            {"success": False, "message": f"No entries found for group '{group_id}'."},
            status=status.HTTP_404_NOT_FOUND,
        )

    serializer = HolidaySerializer(holidays, many=True)
    max_allowed_leaves = holidays.first().max_allowed_leaves

    return Response(
        {
            "success": True,
            "group_id": group_id.upper(),
            "max_allowed_leaves": max_allowed_leaves,
            "dates": serializer.data,
        },
        status=status.HTTP_200_OK,
    )


# ─────────────────────────────────────────────────────────────
# DELETE /api/attendance/holiday/<holiday_id>/delete/
# ─────────────────────────────────────────────────────────────
@api_view(['DELETE'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def delete_holiday(request, holiday_id):
    try:
        holiday = Holiday.objects.get(pk=holiday_id)
    except Holiday.DoesNotExist:
        return Response(
            {"success": False, "message": "Holiday not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    name = holiday.name
    holiday.delete()
    logger.info(f"Holiday deleted: '{name}' (id={holiday_id}) by {request.user}")

    return Response(
        {"success": True, "message": "Holiday deleted successfully."},
        status=status.HTTP_200_OK,
    )


# ═════════════════════════════════════════════════════════════
#  PERMISSION VIEWS
# ═════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# GET /api/attendance/permissions/
# ─────────────────────────────────────────────────────────────
@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def list_permissions(request):
    queryset = Permission.objects.select_related('employee').order_by('-date', '-created_at')

    if not request.user.is_superuser:
        try:
            employee = request.user.employee_profile
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee account not linked. Contact administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )
        queryset = queryset.filter(employee=employee)

    year     = request.query_params.get('year')
    month    = request.query_params.get('month')
    employee = request.query_params.get('employee')

    if year:
        queryset = queryset.filter(date__year=int(year))
    if month:
        queryset = queryset.filter(date__month=int(month))
    if employee and request.user.is_superuser:
        queryset = queryset.filter(employee__id=int(employee))

    serializer = PermissionSerializer(queryset, many=True)
    return Response(
        {"success": True, "permissions": serializer.data},
        status=status.HTTP_200_OK,
    )


# ─────────────────────────────────────────────────────────────
# POST /api/attendance/permissions/add/
# ─────────────────────────────────────────────────────────────
@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def add_permission(request):
    if request.user.is_superuser:
        data = request.data
    else:
        try:
            employee = request.user.employee_profile
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee account not linked. Contact administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = request.data.copy()
        data['employee'] = employee.id

    serializer = PermissionSerializer(data=data)

    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    perm = serializer.save()
    logger.info(
        f"Permission created for employee '{perm.employee}' "
        f"on {perm.date} by {request.user}"
    )
    return Response(
        {
            "success": True,
            "message": "Permission added successfully.",
            "permission": PermissionSerializer(perm).data,
        },
        status=status.HTTP_201_CREATED,
    )


# ─────────────────────────────────────────────────────────────
# GET /api/attendance/permissions/<id>/
# ─────────────────────────────────────────────────────────────
@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def get_permission(request, permission_id):
    try:
        perm = Permission.objects.select_related('employee').get(pk=permission_id)
    except Permission.DoesNotExist:
        return Response(
            {"success": False, "message": "Permission not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not request.user.is_superuser:
        try:
            employee = request.user.employee_profile
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee account not linked. Contact administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if perm.employee != employee:
            return Response(
                {"success": False, "message": "Permission not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    serializer = PermissionSerializer(perm)
    return Response(
        {"success": True, "permission": serializer.data},
        status=status.HTTP_200_OK,
    )


# ─────────────────────────────────────────────────────────────
# PUT /api/attendance/permissions/<id>/edit/
# ─────────────────────────────────────────────────────────────
@api_view(['PUT'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def edit_permission(request, permission_id):
    try:
        perm = Permission.objects.get(pk=permission_id)
    except Permission.DoesNotExist:
        return Response(
            {"success": False, "message": "Permission not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not request.user.is_superuser:
        try:
            employee = request.user.employee_profile
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee account not linked. Contact administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if perm.employee != employee:
            return Response(
                {"success": False, "message": "Permission not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    serializer = PermissionSerializer(perm, data=request.data, partial=False)

    if not serializer.is_valid():
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    perm = serializer.save()
    logger.info(f"Permission (id={permission_id}) updated by {request.user}")
    return Response(
        {
            "success": True,
            "message": "Permission updated successfully.",
            "permission": PermissionSerializer(perm).data,
        },
        status=status.HTTP_200_OK,
    )


# ─────────────────────────────────────────────────────────────
# DELETE /api/attendance/permissions/<id>/delete/
# ─────────────────────────────────────────────────────────────
@api_view(['DELETE'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def delete_permission(request, permission_id):
    try:
        perm = Permission.objects.get(pk=permission_id)
    except Permission.DoesNotExist:
        return Response(
            {"success": False, "message": "Permission not found."},
            status=status.HTTP_404_NOT_FOUND,
        )

    if not request.user.is_superuser:
        try:
            employee = request.user.employee_profile
        except Employee.DoesNotExist:
            return Response(
                {"detail": "Employee account not linked. Contact administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if perm.employee != employee:
            return Response(
                {"success": False, "message": "Permission not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

    perm.delete()
    logger.info(f"Permission (id={permission_id}) deleted by {request.user}")
    return Response(
        {"success": True, "message": "Permission deleted successfully."},
        status=status.HTTP_200_OK,
    )


# ═════════════════════════════════════════════════════════════
#  READ-ONLY VIEWSETS
# ═════════════════════════════════════════════════════════════
class AttendanceLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AttendanceLog.objects.all().order_by('-timestamp')
    serializer_class = AttendanceLogSerializer


class DailyAttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = DailyAttendance.objects.all().order_by('-date')
    serializer_class = DailyAttendanceSerializer


# ═════════════════════════════════════════════════════════════
#  OVERTIME HELPER
# ═════════════════════════════════════════════════════════════

def calculate_extra_hours(check_in, check_out, shift, att_date):
    """
    Calculates extra hours worked outside of the assigned shift.

    Rules:
      - Any time worked BEFORE shift start counts as early OT.
      - Any time worked AFTER shift end counts as late OT.
      - Total extra = (early_mins + late_mins) / 60

    Returns: (extra_hours_float, early_mins_int, late_mins_int)
    """
    if not shift or not check_in or not check_out:
        return 0.0, 0, 0

    # Build full datetime for shift start and end on the attendance date
    shift_start = datetime.combine(att_date, shift.start_time)
    shift_end   = datetime.combine(att_date, shift.end_time)

    # Handle night shifts crossing midnight
    if shift_end <= shift_start:
        shift_end += timedelta(days=1)

    # Normalize to naive datetime for comparison
    ci = check_in.replace(tzinfo=None)  if check_in.tzinfo  else check_in
    co = check_out.replace(tzinfo=None) if check_out.tzinfo else check_out

    # Early check-in OT: positive if employee arrived BEFORE shift start
    early_mins = max(0, int((shift_start - ci).total_seconds() / 60))

    # Late check-out OT: positive if employee left AFTER shift end
    late_mins = max(0, int((co - shift_end).total_seconds() / 60))

    total_extra_mins = early_mins + late_mins
    total_extra_hrs  = round(total_extra_mins / 60, 2)

    return total_extra_hrs, early_mins, late_mins


# ═════════════════════════════════════════════════════════════
#  OVERTIME VIEWS
# ═════════════════════════════════════════════════════════════

MIN_OT_MINUTES = 60  # only records >= 1 h get an OvertimeRecord


# ─────────────────────────────────────────────────────────────
# POST /api/attendance/overtime/generate/
# Body: { "date": "YYYY-MM-DD" }  — omit to use today
# ─────────────────────────────────────────────────────────────
@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def generate_ot_records(request):
    date_str    = request.data.get('date')
    parsed_date = parse_date(date_str) if date_str else timezone.localdate()

    logger.info(f"generate_ot_records called by {request.user}; date_str={date_str}; parsed_date={parsed_date}")

    if not parsed_date:
        logger.warning(f"generate_ot_records: invalid date received: {date_str}")
        return Response({'error': 'Invalid date.'}, status=status.HTTP_400_BAD_REQUEST)

    qs = DailyAttendance.objects.filter(date=parsed_date).select_related(
        'employee', 'employee__shift_assignment__shift'
    )

    total_attendance = qs.count()
    created_count = skipped_count = error_count = 0
    logger.info(f"generate_ot_records: attendance rows for {parsed_date} = {total_attendance}")

    for att in qs:
        logger.info(
            f"Attendance id={att.id}, employee={att.employee_id or att.employee}, "
            f"date={att.date}, check_in={att.check_in}, check_out={att.check_out}, "
            f"extra_hours={att.extra_hours}"
        )

        try:
            try:
                _ = att.overtime
            except OvertimeRecord.DoesNotExist:
                _ = None

            if _ is not None:
                skipped_count += 1
                logger.info(f"Skipping attendance id={att.id}: overtime record already exists.")
                continue

            shift = getattr(getattr(att.employee, 'shift_assignment', None), 'shift', None)
            logger.info(f"Attendance id={att.id}: shift_assignment shift={shift}")

            extra_hrs, early_mins, late_mins = calculate_extra_hours(
                att.check_in, att.check_out, shift, parsed_date
            )
            logger.info(
                f"Attendance id={att.id}: calculate_extra_hours -> "
                f"extra_hrs={extra_hrs}, early_mins={early_mins}, late_mins={late_mins}"
            )

            if not shift:
                extra_hrs = float(att.extra_hours or 0)
                total_mins = int(extra_hrs * 60)
                logger.info(
                    f"Attendance id={att.id}: no shift available, falling back to "
                    f"att.extra_hours={att.extra_hours}, total_mins={total_mins}"
                )
            else:
                total_mins = early_mins + late_mins
                logger.info(
                    f"Attendance id={att.id}: total_mins calculated from early+late = {total_mins}"
                )

            if total_mins < MIN_OT_MINUTES:
                logger.info(
                    f"Skipping attendance id={att.id}: total_mins={total_mins} < {MIN_OT_MINUTES}"
                )
                continue

            OvertimeRecord.objects.create(
                attendance=att,
                extra_hours=extra_hrs,
                early_mins=early_mins,
                late_mins=late_mins,
            )
            created_count += 1
            logger.info(f"Created OvertimeRecord for attendance id={att.id}.")

        except Exception as exc:
            error_count += 1
            logger.exception(
                f"Error processing attendance id={att.id} for OT generation: {exc}"
            )
            continue

    logger.info(
        f"OT generation completed for {parsed_date}: "
        f"{created_count} created, {skipped_count} skipped, {error_count} errors "
        f"by {request.user}"
    )
    return Response(
        {
            'success': True,
            'date':    str(parsed_date),
            'created': created_count,
            'skipped': skipped_count,
            'errors':  error_count,
        },
        status=status.HTTP_201_CREATED,
    )


# ─────────────────────────────────────────────────────────────
# GET /api/attendance/overtime/?year=&month=&department=&status=
# ─────────────────────────────────────────────────────────────
@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def list_ot_records(request):
    qs = OvertimeRecord.objects.select_related(
        'attendance__employee',
        'attendance__employee__shift_assignment__shift',
        'reviewed_by',
    )

    year       = request.query_params.get('year')
    month      = request.query_params.get('month')
    department = request.query_params.get('department')
    ot_status  = request.query_params.get('status')

    if year:
        qs = qs.filter(attendance__date__year=int(year))
    if month:
        qs = qs.filter(attendance__date__month=int(month))
    if department:
        qs = qs.filter(attendance__employee__designation=department)
    if ot_status:
        qs = qs.filter(status=ot_status)

    serializer = OvertimeRecordSerializer(qs, many=True)
    return Response({'success': True, 'results': serializer.data}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────
# POST /api/attendance/overtime/<id>/approve/
# ─────────────────────────────────────────────────────────────
@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def approve_ot_record(request, ot_id):
    try:
        record = OvertimeRecord.objects.get(pk=ot_id)
    except OvertimeRecord.DoesNotExist:
        return Response({'error': 'OT record not found.'}, status=status.HTTP_404_NOT_FOUND)

    record.status      = OvertimeRecord.STATUS_APPROVED
    record.reviewed_by = request.user
    record.reviewed_at = timezone.now()
    record.save()

    logger.info(f"OT record {ot_id} approved by {request.user}")
    return Response({'success': True, 'status': record.status}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────
# POST /api/attendance/overtime/<id>/decline/
# ─────────────────────────────────────────────────────────────
@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def decline_ot_record(request, ot_id):
    try:
        record = OvertimeRecord.objects.get(pk=ot_id)
    except OvertimeRecord.DoesNotExist:
        return Response({'error': 'OT record not found.'}, status=status.HTTP_404_NOT_FOUND)

    record.status      = OvertimeRecord.STATUS_DECLINED
    record.reviewed_by = request.user
    record.reviewed_at = timezone.now()
    record.save()

    logger.info(f"OT record {ot_id} declined by {request.user}")
    return Response({'success': True, 'status': record.status}, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────
# DELETE /api/attendance/overtime/<id>/delete/
# ─────────────────────────────────────────────────────────────
@api_view(['DELETE'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def delete_ot_record(request, ot_id):
    try:
        record = OvertimeRecord.objects.get(pk=ot_id)
    except OvertimeRecord.DoesNotExist:
        return Response({'error': 'OT record not found.'}, status=status.HTTP_404_NOT_FOUND)

    record.delete()
    logger.info(f"OT record {ot_id} deleted by {request.user}")
    return Response({'success': True, 'message': 'OT record deleted.'}, status=status.HTTP_200_OK)