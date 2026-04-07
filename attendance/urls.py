from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views
from .views import (
    AttendanceLogViewSet,
    DailyAttendanceViewSet,
)

app_name = 'attendance'

router = DefaultRouter()
router.register(r'logs',  AttendanceLogViewSet)
router.register(r'daily', DailyAttendanceViewSet)

urlpatterns = [
    # ── Holidays ──────────────────────────────────────────────
    path('holiday/add/',                     views.add_holiday,    name='add_holiday'),
    path('holiday/<int:holiday_id>/delete/', views.delete_holiday, name='delete_holiday'),
    path('calendar/',                        views.get_calendar,   name='get_calendar'),
    path('group/<str:group_id>/',            views.get_group,      name='get_group'),

    # ── Permissions ───────────────────────────────────────────
    path('permissions/',                              views.list_permissions, name='list_permissions'),
    path('permissions/add/',                          views.add_permission,   name='add_permission'),
    path('permissions/<int:permission_id>/',          views.get_permission,   name='get_permission'),
    path('permissions/<int:permission_id>/edit/',     views.edit_permission,  name='edit_permission'),
    path('permissions/<int:permission_id>/delete/',   views.delete_permission,name='delete_permission'),

    # ── Overtime (OvertimeRecord-based) ───────────────────────
    path('overtime/',                        views.list_ot_records,    name='list_ot_records'),
    path('overtime/generate/',               views.generate_ot_records,name='generate_ot_records'),
    path('overtime/<int:ot_id>/approve/',    views.approve_ot_record,  name='approve_ot_record'),
    path('overtime/<int:ot_id>/decline/',    views.decline_ot_record,  name='decline_ot_record'),
    path('overtime/<int:ot_id>/delete/',     views.delete_ot_record,   name='delete_ot_record'),

    # ── Viewsets ──────────────────────────────────────────────
    path('', include(router.urls)),
]