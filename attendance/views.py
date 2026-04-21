from datetime import datetime, timedelta
import json
import logging

from django.utils import timezone
from django.utils.dateparse import parse_date
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model

from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from accounts.authentication import JWTAuthenticationFromCookie
from employee.models import Employee
from .models import (
    Holiday,
    AttendanceLog,
    DailyAttendance,
    EmployeePermission,
    OvertimeRecord,
    OvertimeRequest,
    Leave,
)
from .serializers import (
    HolidaySerializer,
    HolidayCreateSerializer,
    AttendanceLogSerializer,
    DailyAttendanceSerializer,
    OvertimeRecordSerializer,
    OvertimeRequestSerializer,
    OvertimeRequestSubmitSerializer,
    OvertimeRequestModifySerializer,
    OvertimeRequestReviewSerializer,
    OvertimeRequestAssignSerializer,
    OvertimeRequestAdminUpdateSerializer,
    EmployeePermissionRequestSerializer,
    EmployeePermissionReviewSerializer,
    EmployeePermissionCompleteSerializer,
    EmployeePermissionSerializer,
    LeaveRequestSerializer,
    LeaveSerializer,
    LeaveUpdateSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ═════════════════════════════════════════════════════════════
#  PERMISSION EMAIL HELPERS
# ═════════════════════════════════════════════════════════════

def _send_permission_request_email(permission):
    try:
        admin_emails = list(
            User.objects.filter(is_superuser=True)
            .exclude(email="")
            .values_list("email", flat=True)
        )
        if not admin_emails:
            logger.warning("No admin emails found — permission request email skipped.")
            return

        employee     = permission.employee
        perm_type    = "End of Day" if permission.permission_type == "END_DAY" else "Mid Day"
        req_type     = permission.request_type
        expected_fmt = permission.expected_end_time.strftime("%d %b %Y, %I:%M %p")
        date_fmt     = permission.date.strftime("%d %b %Y")

        subject = f"[Permission Request] {employee.full_name} — {perm_type} ({req_type.title()})"

        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        review_url   = f"{frontend_url}/admin/permissions/{permission.id}/review"

        is_preplanned = req_type == EmployeePermission.REQUEST_PREPLANNED

        message = f"""
Hello Admin,

A new {'pre-planned' if is_preplanned else 'emergency'} permission request has been submitted.

──────────────────────────────────────
  Employee     : {employee.full_name}
  Employee ID  : {employee.employee_id}
  Type         : {perm_type}
  Request Type : {req_type.title()}
  Date         : {date_fmt}
  Expected Back: {expected_fmt}
  Reason       : {permission.reason}
──────────────────────────────────────

{'Please click the link below to review and respond to this request:' if is_preplanned else 'This is for your information only — the employee has already departed.'}

{review_url if is_preplanned else ''}

Regards,
Attendance System
        """.strip()

        send_mail(
            subject        = subject,
            message        = message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = admin_emails,
            fail_silently  = False,
        )
        logger.info(f"Permission request email sent to {admin_emails} perm_id={permission.id}")

    except Exception as exc:
        logger.exception(f"Failed to send permission request email: {exc}")


def _send_permission_status_email(permission):
    try:
        employee = permission.employee
        if not hasattr(employee, 'user') or not employee.user.email:
            logger.warning(f"No email for employee {employee} — status email skipped.")
            return

        is_approved  = permission.status == EmployeePermission.STATUS_APPROVED
        status_text  = "APPROVED" if is_approved else "REJECTED"
        status_msg   = "approved" if is_approved else "rejected"
        perm_type    = "End of Day" if permission.permission_type == "END_DAY" else "Mid Day"
        date_fmt     = permission.date.strftime("%d %b %Y")

        subject = f"Permission {status_text}: {perm_type} on {date_fmt}"
        message = f"Your pre-planned permission request has been {status_msg}.\n\nRegards,\nAttendance System"

        send_mail(
            subject        = subject,
            message        = message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [employee.user.email],
            fail_silently  = False,
        )
        logger.info(f"Permission status email sent perm_id={permission.id}")

    except Exception as exc:
        logger.exception(f"Failed to send permission status email: {exc}")


# ═════════════════════════════════════════════════════════════
#  LEAVE EMAIL HELPERS
# ═════════════════════════════════════════════════════════════

def _send_leave_request_email(leave):
    try:
        admin_emails = list(
            User.objects.filter(is_superuser=True)
            .exclude(email="")
            .values_list("email", flat=True)
        )
        if not admin_emails:
            return

        employee           = leave.employee
        leave_type_display = dict(Leave.LEAVE_TYPE_CHOICES).get(leave.leave_type, leave.leave_type)
        start_fmt          = leave.start_date.strftime("%d %b %Y")
        end_fmt            = leave.end_date.strftime("%d %b %Y")
        days               = (leave.end_date - leave.start_date).days + 1
        frontend_url       = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        review_url         = f"{frontend_url}/admin/leaves/{leave.id}/review"

        subject = f"[Leave Request] {employee.full_name} — {leave_type_display}"
        message = (
            f"Hello Admin,\n\nA new leave request has been submitted.\n\n"
            f"  Employee  : {employee.full_name}\n"
            f"  Leave Type: {leave_type_display}\n"
            f"  From      : {start_fmt}\n"
            f"  To        : {end_fmt}\n"
            f"  Days      : {days}\n"
            f"  Reason    : {leave.reason}\n\n"
            f"Review: {review_url}\n\nRegards,\nAttendance System"
        )

        send_mail(
            subject        = subject,
            message        = message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = admin_emails,
            fail_silently  = False,
        )
        logger.info(f"Leave request email sent leave_id={leave.id}")

    except Exception as exc:
        logger.exception(f"Failed to send leave request email: {exc}")


def _send_leave_status_email(leave, old_status=None):
    try:
        employee = leave.employee
        if not employee.user.email:
            return

        is_approved        = leave.status == 'APPROVED'
        status_text        = "APPROVED" if is_approved else "REJECTED"
        status_message     = "approved" if is_approved else "rejected"
        leave_type_display = dict(Leave.LEAVE_TYPE_CHOICES).get(leave.leave_type, leave.leave_type)
        start_fmt          = leave.start_date.strftime("%d %b %Y")
        end_fmt            = leave.end_date.strftime("%d %b %Y")

        subject = f"Leave {status_text}: {leave_type_display} - {employee.full_name}"
        message = f"Your leave request has been {status_message}.\n\nRegards,\nAttendance System"

        send_mail(
            subject        = subject,
            message        = message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [employee.user.email],
            fail_silently  = False,
        )
        logger.info(f"Leave status email sent leave_id={leave.id}")

    except Exception as exc:
        logger.exception(f"Failed to send leave status email: {exc}")


# ═════════════════════════════════════════════════════════════
#  OT REQUEST EMAIL HELPERS (FIXED)
# ═════════════════════════════════════════════════════════════

def _send_ot_request_email(ot_request):
    """Email admins when employee submits an OT request (Scenario 1)."""
    try:
        admin_emails = list(
            User.objects.filter(is_superuser=True)
            .exclude(email="")
            .values_list("email", flat=True)
        )
        if not admin_emails:
            logger.warning("No admin emails — OT request email skipped.")
            return

        employee     = ot_request.employee
        start_fmt    = ot_request.start_date.strftime("%d %b %Y")
        end_fmt      = ot_request.end_date.strftime("%d %b %Y")
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        review_url   = f"{frontend_url}/admin/ot-requests/{ot_request.id}/review"

        subject = f"[OT Request] {employee.full_name} — {start_fmt} to {end_fmt}"
        
        # Build time slots summary with better formatting
        slots_summary = ""
        if ot_request.time_slots:
            slot_lines = []
            for slot in ot_request.time_slots:
                start = slot.get('start_time', '--')
                end = slot.get('end_time', '--')
                slot_lines.append(f"  • {start} – {end}")
            slots_summary = "\n".join(slot_lines)
            slots_count = len(ot_request.time_slots)
        else:
            slots_summary = "  • No time slots specified"
            slots_count = 0

        daily_hours = ot_request.daily_hours if hasattr(ot_request, 'daily_hours') else 0.0
        total_hours = float(ot_request.total_hours) if ot_request.total_hours else 0.0

        message = (
            f"Hello Admin,\n\n"
            f"An overtime request has been submitted and requires your review.\n\n"
            f"──────────────────────────────────────\n"
            f"  Employee  : {employee.full_name}\n"
            f"  Emp ID    : {employee.employee_id}\n"
            f"  From      : {start_fmt}\n"
            f"  To        : {end_fmt}\n"
            f"  Days      : {ot_request.total_days}\n"
            f"  Slots     : {slots_count}\n"
            f"  Daily Slots:\n{slots_summary}\n"
            f"  Daily Hrs : {daily_hours}h\n"
            f"  Total Hrs : {total_hours}h\n"
            f"  Reason    : {ot_request.reason or 'N/A'}\n"
            f"──────────────────────────────────────\n\n"
            f"Review here: {review_url}\n\n"
            f"Regards,\nAttendance System"
        )

        send_mail(
            subject        = subject,
            message        = message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = admin_emails,
            fail_silently  = False,
        )
        logger.info(f"OT request email sent ot_id={ot_request.id}")

    except Exception as exc:
        logger.exception(f"Failed to send OT request email: {exc}")


def _send_ot_status_email(ot_request):
    """Email employee when their OT request is approved or declined (Scenario 1)."""
    try:
        employee = ot_request.employee
        if not hasattr(employee, 'user') or not employee.user.email:
            logger.warning(f"No email for employee {employee} — OT status email skipped.")
            return

        is_approved = ot_request.status == OvertimeRequest.STATUS_APPROVED
        status_text = "APPROVED" if is_approved else "DECLINED"
        status_msg  = "approved" if is_approved else "declined"
        start_fmt   = ot_request.start_date.strftime("%d %b %Y")
        end_fmt     = ot_request.end_date.strftime("%d %b %Y")
        
        # Build time slots summary
        slots_summary = ""
        if ot_request.time_slots:
            slot_lines = []
            for slot in ot_request.time_slots:
                start = slot.get('start_time', '--')
                end = slot.get('end_time', '--')
                slot_lines.append(f"    • {start} – {end}")
            slots_summary = "\n".join(slot_lines)
        else:
            slots_summary = "    • No time slots specified"

        daily_hours = ot_request.daily_hours if hasattr(ot_request, 'daily_hours') else 0.0
        total_hours = float(ot_request.total_hours) if ot_request.total_hours else 0.0

        subject = f"OT Request {status_text} — {start_fmt} to {end_fmt}"
        message = (
            f"Your overtime request has been {status_msg}.\n\n"
            f"  From      : {start_fmt}\n"
            f"  To        : {end_fmt}\n"
            f"  Days      : {ot_request.total_days}\n"
            f"  Daily Slots:\n{slots_summary}\n"
            f"  Daily Hrs : {daily_hours}h\n"
            f"  Total Hrs : {total_hours}h\n"
            f"  Status    : {status_text}\n"
            + (f"  Remarks   : {ot_request.admin_remarks}\n" if ot_request.admin_remarks else "")
            + "\nRegards,\nAttendance System"
        )

        send_mail(
            subject        = subject,
            message        = message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [employee.user.email],
            fail_silently  = False,
        )
        logger.info(f"OT status email sent ot_id={ot_request.id} status={ot_request.status}")

    except Exception as exc:
        logger.exception(f"Failed to send OT status email: {exc}")


def _send_ot_assigned_email(ot_request):
    """Email employee when admin assigns OT to them (Scenario 2)."""
    try:
        employee = ot_request.employee
        if not hasattr(employee, 'user') or not employee.user.email:
            logger.warning(f"No email for employee {employee} — OT assigned email skipped.")
            return

        start_fmt = ot_request.start_date.strftime("%d %b %Y")
        end_fmt   = ot_request.end_date.strftime("%d %b %Y")
        
        # Build time slots summary
        slots_summary = ""
        if ot_request.time_slots:
            slot_lines = []
            for slot in ot_request.time_slots:
                start = slot.get('start_time', '--')
                end = slot.get('end_time', '--')
                slot_lines.append(f"    • {start} – {end}")
            slots_summary = "\n".join(slot_lines)
        else:
            slots_summary = "    • No time slots specified"

        daily_hours = ot_request.daily_hours if hasattr(ot_request, 'daily_hours') else 0.0
        total_hours = float(ot_request.total_hours) if ot_request.total_hours else 0.0
        
        subject   = f"Overtime Assigned — {start_fmt} to {end_fmt}"
        message   = (
            f"An overtime shift has been assigned to you.\n\n"
            f"  From      : {start_fmt}\n"
            f"  To        : {end_fmt}\n"
            f"  Days      : {ot_request.total_days}\n"
            f"  Daily Slots:\n{slots_summary}\n"
            f"  Daily Hrs : {daily_hours}h\n"
            f"  Total Hrs : {total_hours}h\n"
            f"  Status    : APPROVED\n\n"
            f"Regards,\nAttendance System"
        )

        send_mail(
            subject        = subject,
            message        = message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [employee.user.email],
            fail_silently  = False,
        )
        logger.info(f"OT assigned email sent ot_id={ot_request.id} employee={employee}")

    except Exception as exc:
        logger.exception(f"Failed to send OT assigned email: {exc}")


def _send_ot_updated_email(ot_request):
    """Email employee when admin updates their OT (Scenario 2 update)."""
    try:
        employee = ot_request.employee
        if not hasattr(employee, 'user') or not employee.user.email:
            return

        start_fmt = ot_request.start_date.strftime("%d %b %Y")
        end_fmt   = ot_request.end_date.strftime("%d %b %Y")
        
        # Build time slots summary
        slots_summary = ""
        if ot_request.time_slots:
            slot_lines = []
            for slot in ot_request.time_slots:
                start = slot.get('start_time', '--')
                end = slot.get('end_time', '--')
                slot_lines.append(f"    • {start} – {end}")
            slots_summary = "\n".join(slot_lines)
        else:
            slots_summary = "    • No time slots specified"

        daily_hours = ot_request.daily_hours if hasattr(ot_request, 'daily_hours') else 0.0
        total_hours = float(ot_request.total_hours) if ot_request.total_hours else 0.0
        
        subject   = f"Your OT Has Been Updated — {start_fmt} to {end_fmt}"
        message   = (
            f"Your overtime has been updated by admin.\n\n"
            f"  From      : {start_fmt}\n"
            f"  To        : {end_fmt}\n"
            f"  Days      : {ot_request.total_days}\n"
            f"  Daily Slots:\n{slots_summary}\n"
            f"  Daily Hrs : {daily_hours}h\n"
            f"  Total Hrs : {total_hours}h\n\n"
            f"Regards,\nAttendance System"
        )

        send_mail(
            subject        = subject,
            message        = message,
            from_email     = settings.DEFAULT_FROM_EMAIL,
            recipient_list = [employee.user.email],
            fail_silently  = False,
        )
        logger.info(f"OT updated email sent ot_id={ot_request.id}")

    except Exception as exc:
        logger.exception(f"Failed to send OT updated email: {exc}")


# ═════════════════════════════════════════════════════════════
#  HOLIDAY VIEWS
# ═════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def add_holiday(request):
    serializer = HolidayCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    result = serializer.save()

    if isinstance(result, list):
        logger.info(f"Festival created: '{result[0].name}' ({len(result)} dates) by {request.user}")
        return Response(
            {
                "success":     True,
                "message":     f"Festival added successfully with {len(result)} date(s).",
                "group_id":    result[0].group_id,
                "holiday_ids": [h.id for h in result],
                "dates":       [str(h.date) for h in result],
            },
            status=status.HTTP_201_CREATED,
        )

    logger.info(f"Holiday created: '{result.name}' on {result.date} by {request.user}")
    return Response(
        {"success": True, "message": "Holiday added successfully.", "holiday_id": result.id},
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def get_calendar(request):
    queryset = Holiday.objects.all()
    year  = request.query_params.get('year')
    month = request.query_params.get('month')
    if year:  queryset = queryset.filter(date__year=int(year))
    if month: queryset = queryset.filter(date__month=int(month))
    serializer = HolidaySerializer(queryset, many=True)
    return Response({"success": True, "calendar": serializer.data}, status=status.HTTP_200_OK)


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
    serializer         = HolidaySerializer(holidays, many=True)
    max_allowed_leaves = holidays.first().max_allowed_leaves
    return Response(
        {"success": True, "group_id": group_id.upper(), "max_allowed_leaves": max_allowed_leaves, "dates": serializer.data},
        status=status.HTTP_200_OK,
    )


@api_view(['DELETE'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def delete_holiday(request, holiday_id):
    try:
        holiday = Holiday.objects.get(pk=holiday_id)
    except Holiday.DoesNotExist:
        return Response({"success": False, "message": "Holiday not found."}, status=status.HTTP_404_NOT_FOUND)
    name = holiday.name
    holiday.delete()
    logger.info(f"Holiday deleted: '{name}' (id={holiday_id}) by {request.user}")
    return Response({"success": True, "message": "Holiday deleted successfully."}, status=status.HTTP_200_OK)


# ═════════════════════════════════════════════════════════════
#  READ-ONLY VIEWSETS
# ═════════════════════════════════════════════════════════════

class AttendanceLogViewSet(viewsets.ReadOnlyModelViewSet):
    queryset         = AttendanceLog.objects.all().order_by('-timestamp')
    serializer_class = AttendanceLogSerializer


class DailyAttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    queryset         = DailyAttendance.objects.all().order_by('-date')
    serializer_class = DailyAttendanceSerializer


# ═════════════════════════════════════════════════════════════
#  OVERTIME RECORD HELPERS & VIEWS
# ═════════════════════════════════════════════════════════════

def calculate_extra_hours(check_in, check_out, shift, att_date):
    if not shift or not check_in or not check_out:
        return 0.0, 0, 0

    shift_start = datetime.combine(att_date, shift.start_time)
    shift_end   = datetime.combine(att_date, shift.end_time)

    if shift_end <= shift_start:
        shift_end += timedelta(days=1)

    ci = check_in.replace(tzinfo=None)  if check_in.tzinfo  else check_in
    co = check_out.replace(tzinfo=None) if check_out.tzinfo else check_out

    early_mins       = max(0, int((shift_start - ci).total_seconds() / 60))
    late_mins        = max(0, int((co - shift_end).total_seconds() / 60))
    total_extra_mins = early_mins + late_mins
    total_extra_hrs  = round(total_extra_mins / 60, 2)

    return total_extra_hrs, early_mins, late_mins


MIN_OT_MINUTES = 60


@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def generate_ot_records(request):
    date_str    = request.data.get('date')
    parsed_date = parse_date(date_str) if date_str else timezone.localdate()

    if not parsed_date:
        return Response({'error': 'Invalid date.'}, status=status.HTTP_400_BAD_REQUEST)

    qs = DailyAttendance.objects.filter(date=parsed_date).select_related(
        'employee', 'employee__shift_assignment__shift'
    )

    created_count = skipped_count = error_count = 0

    for att in qs:
        try:
            try:
                _ = att.overtime
            except OvertimeRecord.DoesNotExist:
                _ = None

            if _ is not None:
                skipped_count += 1
                continue

            shift = getattr(getattr(att.employee, 'shift_assignment', None), 'shift', None)
            extra_hrs, early_mins, late_mins = calculate_extra_hours(
                att.check_in, att.check_out, shift, parsed_date
            )

            if not shift:
                extra_hrs  = float(att.extra_hours or 0)
                total_mins = int(extra_hrs * 60)
            else:
                total_mins = early_mins + late_mins

            if total_mins < MIN_OT_MINUTES:
                continue

            OvertimeRecord.objects.create(
                attendance  = att,
                extra_hours = extra_hrs,
                early_mins  = early_mins,
                late_mins   = late_mins,
            )
            created_count += 1

        except Exception as exc:
            error_count += 1
            logger.exception(f"Error processing attendance id={att.id}: {exc}")
            continue

    return Response(
        {'success': True, 'date': str(parsed_date), 'created': created_count, 'skipped': skipped_count, 'errors': error_count},
        status=status.HTTP_201_CREATED,
    )


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
    if year:       qs = qs.filter(attendance__date__year=int(year))
    if month:      qs = qs.filter(attendance__date__month=int(month))
    if department: qs = qs.filter(attendance__employee__designation=department)
    if ot_status:  qs = qs.filter(status=ot_status)
    serializer = OvertimeRecordSerializer(qs, many=True)
    return Response({'success': True, 'results': serializer.data}, status=status.HTTP_200_OK)


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
    return Response({'success': True, 'status': record.status}, status=status.HTTP_200_OK)


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
    return Response({'success': True, 'status': record.status}, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def delete_ot_record(request, ot_id):
    try:
        record = OvertimeRecord.objects.get(pk=ot_id)
    except OvertimeRecord.DoesNotExist:
        return Response({'error': 'OT record not found.'}, status=status.HTTP_404_NOT_FOUND)
    record.delete()
    return Response({'success': True, 'message': 'OT record deleted.'}, status=status.HTTP_200_OK)


def _resolve_employee(request):
    if request.user.is_superuser:
        emp_pk = (
            request.query_params.get("employee_id")
            or request.data.get("employee_id")
        )
        if emp_pk:
            try:
                return Employee.objects.get(pk=emp_pk), None
            except Employee.DoesNotExist:
                return None, Response(
                    {"detail": "Employee not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
    try:
        return request.user.employee_profile, None
    except Employee.DoesNotExist:
        return None, Response(
            {"detail": "Employee account not linked. Contact administrator."},
            status=status.HTTP_403_FORBIDDEN,
        )


# ═════════════════════════════════════════════════════════════
#  EMPLOYEE PERMISSION VIEWS
# ═════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def emp_permission_request(request):
    employee, err = _resolve_employee(request)
    if err:
        return err

    serializer = EmployeePermissionRequestSerializer(
        data=request.data,
        context={"employee": employee},
    )
    if not serializer.is_valid():
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    perm = serializer.save()
    _send_permission_request_email(perm)

    logger.info(f"EmployeePermission requested: employee={employee} status={perm.status}")
    return Response(
        {"success": True, "message": "Permission request submitted.", "permission": EmployeePermissionSerializer(perm).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def emp_permission_review(request, permission_id):
    if not request.user.is_superuser:
        return Response(
            {"success": False, "message": "Only admins can review permissions."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        perm = EmployeePermission.objects.select_related('employee').get(pk=permission_id)
    except EmployeePermission.DoesNotExist:
        return Response({"success": False, "message": "Permission not found."}, status=status.HTTP_404_NOT_FOUND)

    if perm.request_type != EmployeePermission.REQUEST_PREPLANNED:
        return Response(
            {"success": False, "message": "Only pre-planned permissions can be reviewed."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if perm.status != EmployeePermission.STATUS_PENDING:
        return Response(
            {"success": False, "message": f"Permission is already {perm.status}. Cannot change."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    serializer = EmployeePermissionReviewSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    perm.status        = serializer.validated_data['status']
    perm.reviewed_by   = request.user
    perm.reviewed_at   = timezone.now()
    perm.admin_remarks = serializer.validated_data.get('admin_remarks', '')
    perm.save()

    _send_permission_status_email(perm)

    logger.info(f"EmployeePermission {perm.status}: perm_id={permission_id} by admin={request.user}")
    return Response(
        {"success": True, "message": f"Permission {perm.status.lower()} successfully.", "permission": EmployeePermissionSerializer(perm).data},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def emp_permission_start(request, permission_id):
    employee, err = _resolve_employee(request)
    if err:
        return err

    try:
        perm = EmployeePermission.objects.select_related('employee').get(pk=permission_id)
    except EmployeePermission.DoesNotExist:
        return Response({"success": False, "message": "Permission not found."}, status=status.HTTP_404_NOT_FOUND)

    if not request.user.is_superuser and perm.employee != employee:
        return Response({"success": False, "message": "Permission not found."}, status=status.HTTP_404_NOT_FOUND)

    if perm.status != EmployeePermission.STATUS_APPROVED:
        return Response(
            {"success": False, "message": f"Permission is {perm.status}. Only APPROVED permissions can be started."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    perm.status     = EmployeePermission.STATUS_ACTIVE
    perm.start_time = timezone.now()
    perm.save()

    logger.info(f"EmployeePermission started: perm_id={permission_id} employee={employee}")
    return Response(
        {"success": True, "message": "Permission started.", "permission": EmployeePermissionSerializer(perm).data},
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def emp_permission_complete(request, permission_id):
    employee, err = _resolve_employee(request)
    if err:
        return err

    try:
        perm = EmployeePermission.objects.select_related('employee').get(pk=permission_id)
    except EmployeePermission.DoesNotExist:
        return Response({"success": False, "message": "Permission not found."}, status=status.HTTP_404_NOT_FOUND)

    if not request.user.is_superuser and perm.employee != employee:
        return Response({"success": False, "message": "Permission not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = EmployeePermissionCompleteSerializer(
        data=request.data,
        context={"permission": perm},
    )
    if not serializer.is_valid():
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    perm = serializer.save()

    if perm.status == EmployeePermission.STATUS_COMPLETED:
        return Response(
            {"success": True, "message": "Permission completed successfully.", "permission": EmployeePermissionSerializer(perm).data},
            status=status.HTTP_200_OK,
        )

    return Response(
        {"success": False, "message": "Permission rejected: location is outside the office radius.", "permission": EmployeePermissionSerializer(perm).data},
        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def emp_permission_list(request):
    qs = EmployeePermission.objects.select_related('employee').order_by('-created_at')

    if not request.user.is_superuser:
        employee, err = _resolve_employee(request)
        if err:
            return err
        qs = qs.filter(employee=employee)

    year         = request.query_params.get('year')
    month        = request.query_params.get('month')
    emp_id       = request.query_params.get('employee_id')
    emp_alias    = request.query_params.get('employee') 
    perm_stat    = request.query_params.get('status')
    perm_type    = request.query_params.get('type')
    request_type = request.query_params.get('request_type')

    if year:         qs = qs.filter(date__year=int(year))
    if month:        qs = qs.filter(date__month=int(month))
    if perm_stat:    qs = qs.filter(status=perm_stat.upper())
    if perm_type:    qs = qs.filter(permission_type=perm_type.upper())
    if request_type: qs = qs.filter(request_type=request_type.upper())
    
    # 👇 UPDATE THIS SECTION - support both 'employee_id' and 'employee'
    if request.user.is_superuser:
        # Use employee_id if provided, otherwise check employee alias
        employee_filter = emp_id or emp_alias
        if employee_filter:
            qs = qs.filter(employee__id=int(employee_filter))

    serializer = EmployeePermissionSerializer(qs, many=True)
    return Response(
        {"success": True, "count": qs.count(), "permissions": serializer.data},
        status=status.HTTP_200_OK,
    )

@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def emp_permission_detail(request, permission_id):
    try:
        perm = EmployeePermission.objects.select_related('employee').get(pk=permission_id)
    except EmployeePermission.DoesNotExist:
        return Response({"success": False, "message": "Permission not found."}, status=404)

    if request.user.is_superuser:
        return Response({"success": True, "permission": EmployeePermissionSerializer(perm).data})

    employee, err = _resolve_employee(request)
    if err:
        return err
    if perm.employee != employee:
        return Response({"success": False, "message": "Permission not found."}, status=404)

    return Response({"success": True, "permission": EmployeePermissionSerializer(perm).data})


@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def emp_permission_active(request):
    employee, err = _resolve_employee(request)
    if err:
        return err

    perm = (
        EmployeePermission.objects
        .filter(
            employee=employee,
            status__in=[
                EmployeePermission.STATUS_PENDING,
                EmployeePermission.STATUS_APPROVED,
                EmployeePermission.STATUS_ACTIVE,
            ],
        )
        .select_related('employee')
        .order_by('-created_at')
        .first()
    )

    return Response(
        {"success": True, "active": EmployeePermissionSerializer(perm).data if perm else None},
        status=status.HTTP_200_OK,
    )


@api_view(['DELETE'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def emp_permission_cancel(request, permission_id):
    employee, err = _resolve_employee(request)
    if err:
        return err

    try:
        perm = EmployeePermission.objects.get(pk=permission_id)
    except EmployeePermission.DoesNotExist:
        return Response({"success": False, "message": "Permission not found."}, status=status.HTTP_404_NOT_FOUND)

    if not request.user.is_superuser and perm.employee != employee:
        return Response({"success": False, "message": "Permission not found."}, status=status.HTTP_404_NOT_FOUND)

    cancellable = [EmployeePermission.STATUS_PENDING, EmployeePermission.STATUS_ACTIVE]
    if perm.status not in cancellable:
        return Response(
            {"success": False, "message": f"Cannot cancel a {perm.status} permission."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    perm.delete()
    logger.info(f"EmployeePermission id={permission_id} cancelled by user={request.user}")
    return Response({"success": True, "message": "Permission cancelled successfully."}, status=status.HTTP_200_OK)


# ═════════════════════════════════════════════════════════════
#  LEAVE VIEWS
# ═════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def leave_request(request):
    employee, err = _resolve_employee(request)
    if err:
        return err

    serializer = LeaveRequestSerializer(data=request.data, context={"employee": employee})
    if not serializer.is_valid():
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    leave = serializer.save()
    _send_leave_request_email(leave)

    logger.info(f"Leave requested: employee={employee} from={leave.start_date} to={leave.end_date}")
    return Response(
        {"success": True, "message": "Leave request submitted successfully.", "leave": LeaveSerializer(leave).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def leave_list(request):
    qs = Leave.objects.select_related('employee', 'employee__user').all()

    if not request.user.is_superuser:
        employee, err = _resolve_employee(request)
        if err:
            return err
        qs = qs.filter(employee=employee)

    status_filter = request.query_params.get('status')
    leave_type    = request.query_params.get('leave_type')
    year          = request.query_params.get('year')
    month         = request.query_params.get('month')
    employee_id   = request.query_params.get('employee_id')

    if status_filter: qs = qs.filter(status=status_filter.upper())
    if leave_type:    qs = qs.filter(leave_type=leave_type.upper())
    if year:          qs = qs.filter(start_date__year=int(year))
    if month:         qs = qs.filter(start_date__month=int(month))
    if employee_id and request.user.is_superuser:
        qs = qs.filter(employee__id=int(employee_id))

    serializer = LeaveSerializer(qs, many=True)
    return Response({"success": True, "count": qs.count(), "leaves": serializer.data}, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def leave_detail(request, leave_id):
    try:
        leave = Leave.objects.select_related('employee', 'employee__user').get(pk=leave_id)
    except Leave.DoesNotExist:
        return Response({"success": False, "message": "Leave not found."}, status=status.HTTP_404_NOT_FOUND)

    if not request.user.is_superuser:
        employee, err = _resolve_employee(request)
        if err:
            return err
        if leave.employee != employee:
            return Response({"success": False, "message": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

    return Response({"success": True, "leave": LeaveSerializer(leave).data}, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def leave_review(request, leave_id):
    if not request.user.is_superuser:
        return Response({"success": False, "message": "Only admins can review leaves."}, status=status.HTTP_403_FORBIDDEN)

    try:
        leave = Leave.objects.select_related('employee', 'employee__user').get(pk=leave_id)
    except Leave.DoesNotExist:
        return Response({"success": False, "message": "Leave not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = LeaveUpdateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    if leave.status != 'PENDING':
        return Response(
            {"success": False, "message": f"Leave already {leave.status}. Cannot change."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    old_status          = leave.status
    leave.status        = serializer.validated_data['status']
    leave.reviewed_at   = timezone.now()
    leave.reviewed_by   = request.user
    leave.admin_remarks = serializer.validated_data.get('admin_remarks', '')
    leave.save()

    _send_leave_status_email(leave, old_status)

    logger.info(f"Leave {leave.status}: leave_id={leave_id} by admin={request.user}")
    return Response(
        {"success": True, "message": f"Leave {leave.status.lower()} successfully.", "leave": LeaveSerializer(leave).data},
        status=status.HTTP_200_OK,
    )


@api_view(['DELETE'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def leave_cancel(request, leave_id):
    try:
        leave = Leave.objects.get(pk=leave_id)
    except Leave.DoesNotExist:
        return Response({"success": False, "message": "Leave not found."}, status=status.HTTP_404_NOT_FOUND)

    if not request.user.is_superuser:
        employee, err = _resolve_employee(request)
        if err:
            return err
        if leave.employee != employee:
            return Response({"success": False, "message": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

    if leave.status != 'PENDING':
        return Response(
            {"success": False, "message": f"Cannot cancel a {leave.status} leave request."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    leave.delete()
    logger.info(f"Leave id={leave_id} cancelled by user={request.user}")
    return Response({"success": True, "message": "Leave request cancelled successfully."}, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def leave_stats(request):
    employee, err = _resolve_employee(request)
    if err:
        return err

    current_year = timezone.now().year

    total_approved = Leave.objects.filter(employee=employee, status='APPROVED', start_date__year=current_year).count()
    total_pending  = Leave.objects.filter(employee=employee, status='PENDING').count()
    total_rejected = Leave.objects.filter(employee=employee, status='REJECTED', start_date__year=current_year).count()

    approved_leaves = Leave.objects.filter(employee=employee, status='APPROVED', start_date__year=current_year)
    total_days = sum((l.end_date - l.start_date).days + 1 for l in approved_leaves)

    return Response(
        {
            "success": True,
            "stats": {
                "total_approved":  total_approved,
                "total_pending":   total_pending,
                "total_rejected":  total_rejected,
                "total_days_used": total_days,
                "year":            current_year,
            },
        },
        status=status.HTTP_200_OK,
    )


# ═════════════════════════════════════════════════════════════
#  OVERTIME REQUEST VIEWS
# ═════════════════════════════════════════════════════════════

@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def ot_request_submit(request):
    """
    Employee submits an OT request for a date range.
    Creates: source=employee, status=pending, is_active=True.
    Emails all admins with a review link.
    """
    employee, err = _resolve_employee(request)
    if err:
        return err

    serializer = OvertimeRequestSubmitSerializer(
        data=request.data,
        context={'employee': employee, 'request': request},
    )
    if not serializer.is_valid():
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    ot = serializer.save()
    _send_ot_request_email(ot)

    logger.info(
        f"OT request submitted: employee={employee} "
        f"{ot.start_date}→{ot.end_date} ot_id={ot.id}"
    )
    return Response(
        {
            "success":    True,
            "message":    "OT request submitted successfully.",
            "ot_request": OvertimeRequestSerializer(ot).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def ot_request_modify(request, ot_id):
    """
    Admin modifies a PENDING employee OT request (disable + recreate).
    Rule: ONLY pending requests can be modified. Approved = locked forever.
    """
    if not request.user.is_superuser:
        return Response(
            {"success": False, "message": "Only admins can modify OT requests."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        ot = OvertimeRequest.objects.select_related('employee').get(pk=ot_id)
    except OvertimeRequest.DoesNotExist:
        return Response({"success": False, "message": "OT request not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = OvertimeRequestModifySerializer(
        data=request.data,
        context={'ot_request': ot, 'request': request},
    )
    if not serializer.is_valid():
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    new_ot = serializer.save()

    logger.info(
        f"OT request modified by admin={request.user}: "
        f"old_ot_id={ot_id} new_ot_id={new_ot.id} employee={ot.employee}"
    )
    return Response(
        {
            "success":    True,
            "message":    "OT request modified. Old record disabled, new record created.",
            "ot_request": OvertimeRequestSerializer(new_ot).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def ot_request_review(request, ot_id):
    """
    Admin approves or declines a pending OT request.

    GLOBAL RULE: disable old record + create new record with final status.
    Once approved: can_modify=False (locked forever — source=employee approved records).
    Emails employee with the decision.
    """
    if not request.user.is_superuser:
        return Response(
            {"success": False, "message": "Only admins can review OT requests."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        ot = OvertimeRequest.objects.select_related('employee').get(pk=ot_id)
    except OvertimeRequest.DoesNotExist:
        return Response({"success": False, "message": "OT request not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = OvertimeRequestReviewSerializer(
        data=request.data,
        context={'ot_request': ot, 'request': request},
    )
    if not serializer.is_valid():
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    new_ot = serializer.save()
    _send_ot_status_email(new_ot)

    logger.info(
        f"OT request {new_ot.status}: old_ot_id={ot_id} new_ot_id={new_ot.id} "
        f"by admin={request.user} employee={new_ot.employee}"
    )
    return Response(
        {
            "success":    True,
            "message":    f"OT request {new_ot.status} successfully.",
            "ot_request": OvertimeRequestSerializer(new_ot).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def ot_request_assign(request):
    """
    Admin assigns OT to one or more employees for a date range.
    Creates: source=admin, status=approved, is_active=True.
    No review flow — immediately effective.
    If employee has an overlapping active OT, that is disabled first.
    Emails each employee.
    """
    if not request.user.is_superuser:
        return Response(
            {"success": False, "message": "Only admins can assign OT."},
            status=status.HTTP_403_FORBIDDEN,
        )

    serializer = OvertimeRequestAssignSerializer(
        data=request.data,
        context={'request': request},
    )
    if not serializer.is_valid():
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    created_ots = serializer.save()

    for ot in created_ots:
        _send_ot_assigned_email(ot)

    logger.info(
        f"OT assigned by admin={request.user} to {len(created_ots)} employee(s) "
        f"{request.data.get('start_date')}→{request.data.get('end_date')}"
    )
    return Response(
        {
            "success":     True,
            "message":     f"OT assigned to {len(created_ots)} employee(s) successfully.",
            "ot_requests": OvertimeRequestSerializer(created_ots, many=True).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def ot_request_admin_update(request, ot_id):
    """
    Admin updates an admin-assigned OT record (disable + recreate).
    Old record → is_active=False. New record → source=admin, status=approved.
    Emails employee about the update.
    """
    if not request.user.is_superuser:
        return Response(
            {"success": False, "message": "Only admins can update OT records."},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        ot = OvertimeRequest.objects.select_related('employee').get(pk=ot_id)
    except OvertimeRequest.DoesNotExist:
        return Response({"success": False, "message": "OT request not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = OvertimeRequestAdminUpdateSerializer(
        data=request.data,
        context={'ot_request': ot, 'request': request},
    )
    if not serializer.is_valid():
        return Response({"success": False, "errors": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    new_ot = serializer.save()
    _send_ot_updated_email(new_ot)

    logger.info(
        f"OT updated by admin={request.user}: "
        f"old_ot_id={ot_id} new_ot_id={new_ot.id} employee={ot.employee}"
    )
    return Response(
        {
            "success":    True,
            "message":    "OT updated. Old record disabled, new record created. Employee notified.",
            "ot_request": OvertimeRequestSerializer(new_ot).data,
        },
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def ot_request_list(request):
    """
    List OT requests.
    • Employees: only their own active records (is_active=True).
    • Admins: all records, filterable by is_active, employee_id, status, source, date range.
    Filters: year, month, start_date, end_date, source, status, is_active, employee_id.
    """
    qs = OvertimeRequest.objects.select_related(
        'employee', 'reviewed_by', 'created_by', 'replaced_by'
    )

    if not request.user.is_superuser:
        employee, err = _resolve_employee(request)
        if err:
            return err
        qs = qs.filter(employee=employee, is_active=True)
    else:
        is_active_param = request.query_params.get('is_active')
        if is_active_param is not None:
            qs = qs.filter(is_active=is_active_param.lower() == 'true')

        employee_id = request.query_params.get('employee_id')
        if employee_id:
            qs = qs.filter(employee__id=int(employee_id))

    year       = request.query_params.get('year')
    month      = request.query_params.get('month')
    start_date = request.query_params.get('start_date')  
    end_date   = request.query_params.get('end_date')   
    src        = request.query_params.get('source')
    stat       = request.query_params.get('status')

    if year:       qs = qs.filter(start_date__year=int(year))
    if month:      qs = qs.filter(start_date__month=int(month))
    if start_date: qs = qs.filter(start_date__gte=start_date)
    if end_date:   qs = qs.filter(end_date__lte=end_date)
    if src:        qs = qs.filter(source=src.lower())
    if stat:       qs = qs.filter(status=stat.lower())

    serializer = OvertimeRequestSerializer(qs, many=True)
    return Response(
        {"success": True, "count": qs.count(), "ot_requests": serializer.data},
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def ot_request_detail(request, ot_id):
    """Get a single OT request. Employees can only view their own."""
    try:
        ot = OvertimeRequest.objects.select_related(
            'employee', 'reviewed_by', 'created_by', 'replaced_by'
        ).get(pk=ot_id)
    except OvertimeRequest.DoesNotExist:
        return Response({"success": False, "message": "OT request not found."}, status=status.HTTP_404_NOT_FOUND)

    if not request.user.is_superuser:
        employee, err = _resolve_employee(request)
        if err:
            return err
        if ot.employee != employee:
            return Response({"success": False, "message": "OT request not found."}, status=status.HTTP_404_NOT_FOUND)

    return Response(
        {"success": True, "ot_request": OvertimeRequestSerializer(ot).data},
        status=status.HTTP_200_OK,
    )


@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def ot_request_history(request):
    """
    Admin view: full audit trail — all records including disabled ones.
    Filter by employee_id and/or date range to see a specific OT's history chain.
    """
    if not request.user.is_superuser:
        return Response(
            {"success": False, "message": "Only admins can view OT history."},
            status=status.HTTP_403_FORBIDDEN,
        )

    qs = OvertimeRequest.objects.select_related(
        'employee', 'reviewed_by', 'created_by', 'replaced_by'
    )

    employee_id = request.query_params.get('employee_id')
    start_date  = request.query_params.get('start_date')
    end_date    = request.query_params.get('end_date')
    year        = request.query_params.get('year')
    month       = request.query_params.get('month')

    if employee_id: qs = qs.filter(employee__id=int(employee_id))
    if start_date:  qs = qs.filter(start_date__gte=start_date)
    if end_date:    qs = qs.filter(end_date__lte=end_date)
    if year:        qs = qs.filter(start_date__year=int(year))
    if month:       qs = qs.filter(start_date__month=int(month))

    serializer = OvertimeRequestSerializer(qs, many=True)
    return Response(
        {"success": True, "count": qs.count(), "history": serializer.data},
        status=status.HTTP_200_OK,
    )