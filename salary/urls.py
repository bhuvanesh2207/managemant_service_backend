from django.urls import path
from .views import generate_salary, salary_list

urlpatterns = [
    path('generate/', generate_salary, name='generate_salary'),
    path('list/', salary_list, name='salary_list'),
]