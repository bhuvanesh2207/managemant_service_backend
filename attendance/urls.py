from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import AttendanceLogViewSet, DailyAttendanceViewSet

app_name = 'attendance'

router = DefaultRouter()
router.register(r'logs',  AttendanceLogViewSet)
router.register(r'daily', DailyAttendanceViewSet)

urlpatterns = [

    # ── Holidays ──────────────────────────────────────────────────────────
    path('holiday/add/',                     views.add_holiday,    name='add_holiday'),
    path('holiday/<int:holiday_id>/delete/', views.delete_holiday, name='delete_holiday'),
    path('calendar/',                        views.get_calendar,   name='get_calendar'),
    path('group/<str:group_id>/',            views.get_group,      name='get_group'),

    # ── Overtime Record (auto-generated from check-in/out) ────────────────
    path('overtime/',                         views.list_ot_records,     name='list_ot_records'),
    path('overtime/generate/',                views.generate_ot_records,  name='generate_ot_records'),
    path('overtime/<int:ot_id>/approve/',     views.approve_ot_record,   name='approve_ot_record'),
    path('overtime/<int:ot_id>/decline/',     views.decline_ot_record,   name='decline_ot_record'),
    path('overtime/<int:ot_id>/delete/',      views.delete_ot_record,    name='delete_ot_record'),

    # ── Overtime Requests (Scenario 1 + Scenario 2) ───────────────────────

    path('ot-requests/',                          views.ot_request_list,         name='ot_request_list'),
    path('ot-requests/submit/',                   views.ot_request_submit,       name='ot_request_submit'),
    path('ot-requests/assign/',                   views.ot_request_assign,       name='ot_request_assign'),
    path('ot-requests/history/',                  views.ot_request_history,      name='ot_request_history'),
    path('ot-requests/<int:ot_id>/',              views.ot_request_detail,       name='ot_request_detail'),
    path('ot-requests/<int:ot_id>/modify/',       views.ot_request_modify,       name='ot_request_modify'),
    path('ot-requests/<int:ot_id>/review/',       views.ot_request_review,       name='ot_request_review'),
    path('ot-requests/<int:ot_id>/update/',       views.ot_request_admin_update, name='ot_request_admin_update'),

    # ── Permissions (Clean URLs) ──────────────────────────────────────────
    path('permissions/',                              views.emp_permission_list,     name='permission_list'),
    path('permissions/request/',                      views.emp_permission_request,  name='permission_request'),
    path('permissions/active/',                       views.emp_permission_active,   name='permission_active'),
    path('permissions/<int:permission_id>/',          views.emp_permission_detail,   name='permission_detail'),
    path('permissions/<int:permission_id>/review/',   views.emp_permission_review,   name='permission_review'),
    path('permissions/<int:permission_id>/start/',    views.emp_permission_start,    name='permission_start'),
    path('permissions/<int:permission_id>/complete/', views.emp_permission_complete, name='permission_complete'),
    path('permissions/<int:permission_id>/cancel/',   views.emp_permission_cancel,   name='permission_cancel'),

    # ── Leave Management ──────────────────────────────────────────────────
    path('leaves/request/',                views.leave_request, name='leave_request'),
    path('leaves/',                        views.leave_list,    name='leave_list'),
    path('leaves/stats/',                  views.leave_stats,   name='leave_stats'),
    path('leaves/<int:leave_id>/',         views.leave_detail,  name='leave_detail'),
    path('leaves/<int:leave_id>/review/',  views.leave_review,  name='leave_review'),
    path('leaves/<int:leave_id>/cancel/',  views.leave_cancel,  name='leave_cancel'),

    # ── Viewsets ──────────────────────────────────────────────────────────
    path('', include(router.urls)),
]