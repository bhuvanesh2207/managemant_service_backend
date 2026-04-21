from django.urls import path, include, re_path
from . import views
from rest_framework.routers import DefaultRouter
from .views import WorkShiftViewSet, EmployeeShiftViewSet, EmployeeProfileView

router = DefaultRouter()
router.register(r'shifts', WorkShiftViewSet)
router.register(r'employee-shifts', EmployeeShiftViewSet)

urlpatterns = [
    path('', include(router.urls)),

    path('profile/', EmployeeProfileView.as_view(), name='employee-profile'),

    path('add/', views.add_employee, name='employee-add'),
    path('list/', views.list_employees, name='employee-list'),
    path('me/', views.get_my_employee, name='employee-me'),
    path('<int:employee_id>/', views.get_employee, name='employee-detail'),
    path('update/<int:employee_id>/', views.update_employee, name='employee-update'),
    path('delete/<int:employee_id>/', views.delete_employee, name='employee-delete'), 

    re_path(r'^media/(?P<file_path>.+)$', views.serve_employee_file, name='serve_employee_file'),
]