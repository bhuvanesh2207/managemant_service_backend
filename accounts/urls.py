from django.urls import path
from .views import (
    # ── Existing auth ──────────────────────────────────────
    LoginView,
    AdminRefreshTokenView,
    AdminLogoutView,
    CheckAuthView,
    # ── Forgot password ────────────────────────────────────
    ForgotPasswordSendOTPView,
    ForgotPasswordVerifyOTPView,
    ForgotPasswordResetView,
)

from .views import save_email_config, get_email_config

urlpatterns = [
    # ── Auth ───────────────────────────────────────────────
    path("login/",      LoginView.as_view(),        name="login"),
    path("refresh/",    AdminRefreshTokenView.as_view(), name="refresh"),
    path("logout/",     AdminLogoutView.as_view(),       name="logout"),
    path("check_auth/", CheckAuthView.as_view(),         name="check-auth"),

    # ── Forgot password (3-step flow) ──────────────────────
    path("forgot-password/send-otp/",   ForgotPasswordSendOTPView.as_view(),   name="forgot-send-otp"),
    path("forgot-password/verify-otp/", ForgotPasswordVerifyOTPView.as_view(), name="forgot-verify-otp"),
    path("forgot-password/reset/",      ForgotPasswordResetView.as_view(),     name="forgot-reset"),

    path("email-config/save/", save_email_config, name="email-config-save"),
    path("email-config/get/",  get_email_config,  name="email-config-get"),
]