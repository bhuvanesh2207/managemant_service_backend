from django.urls import path
from .views import generate_salary

urlpatterns = [
    path('generate/', generate_salary, name='generate_salary'),
]