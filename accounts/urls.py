from django.urls import path
from .views import (
    LoginView,
    AdminLogoutView,
    AdminRefreshTokenView,
    CheckAuthView,
    EmployeeChangePasswordView,  
    ForgotPasswordSendOTPView,
    ForgotPasswordVerifyOTPView,
    ForgotPasswordResetView,
    save_email_config,
    get_email_config,
)

urlpatterns = [
    path('login/',           LoginView.as_view(),              name='login'),
    path('logout/',          AdminLogoutView.as_view(),         name='logout'),
    path('token/refresh/',   AdminRefreshTokenView.as_view(),   name='token_refresh'),
    path('check_auth/',      CheckAuthView.as_view(),           name='check_auth'),

    path('change-password/', EmployeeChangePasswordView.as_view(), name='change_password'),

    path('forgot-password/send-otp/',   ForgotPasswordSendOTPView.as_view()),
    path('forgot-password/verify-otp/', ForgotPasswordVerifyOTPView.as_view()),
    path('forgot-password/reset/',      ForgotPasswordResetView.as_view()),

    path('email-config/',        get_email_config,  name='get_email_config'),
    path('email-config/save/',   save_email_config, name='save_email_config'),
]