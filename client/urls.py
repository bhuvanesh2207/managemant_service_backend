from django.urls import path
from . import views

urlpatterns = [
    path("add/", views.add_client),
    path("list/", views.list_clients),
    path("<int:client_id>/", views.get_client),
    path("update/<int:client_id>/", views.update_client),
    path("delete/<int:client_id>/", views.delete_client),
    path("names/", views.get_client_names),
]
