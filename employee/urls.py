from django.urls import path, include, re_path
from . import views
from rest_framework.routers import DefaultRouter
from .views import WorkShiftViewSet, EmployeeShiftViewSet

router = DefaultRouter()
router.register(r'shifts', WorkShiftViewSet)
router.register(r'employee-shifts', EmployeeShiftViewSet)

urlpatterns = [
    path('', include(router.urls)),

    path('add/', views.add_employee),
    path('list/', views.list_employees),
    path('<int:employee_id>/', views.get_employee),
    path('update/<int:employee_id>/', views.update_employee),
    path('delete/<int:employee_id>/', views.delete_employee),

    # ✅ Secure media serving — must be last
    re_path(r'^media/(?P<file_path>.+)$', views.serve_employee_file, name='serve_employee_file'),
]