from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.list_domains, name='domain-list'),
    path('add/', views.add_domain, name='domain-add'),
    path('get/<int:domain_id>/', views.get_domain, name='domain-detail'),
    path('update/<int:domain_id>/', views.update_domain, name='domain-update'),
    path('delete/<int:domain_id>/', views.delete_domain, name='domain-delete'),
    path('history/', views.get_domain_history, name='domain-history-all'),
    path('history/<int:domain_id>/', views.get_domain_history, name='domain-history'),
]
