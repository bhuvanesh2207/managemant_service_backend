from django.urls import path
from .views import AdminLoginView, AdminRefreshTokenView, AdminLogoutView

urlpatterns = [
    path("login/", AdminLoginView.as_view(), name="admin-login"),
    path('refresh/', AdminRefreshTokenView.as_view(), name='admin-refresh'),
    path('logout/', AdminLogoutView.as_view(), name='admin-logout'),

]
