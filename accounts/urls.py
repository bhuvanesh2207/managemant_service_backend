from django.urls import path
from .views import (
    # ── Existing auth ──────────────────────────────────────
    AdminLoginView,
    AdminRefreshTokenView,
    AdminLogoutView,
    AdminMeView,
    # ── Forgot password ────────────────────────────────────
    ForgotPasswordSendOTPView,
    ForgotPasswordVerifyOTPView,
    ForgotPasswordResetView,
)

urlpatterns = [
    # ── Auth ───────────────────────────────────────────────
    path("login/",      AdminLoginView.as_view(),        name="admin-login"),
    path("refresh/",    AdminRefreshTokenView.as_view(), name="admin-refresh"),
    path("logout/",     AdminLogoutView.as_view(),       name="admin-logout"),
    path("check_auth/", AdminMeView.as_view(),           name="admin-me"),

    # ── Forgot password (3-step flow) ──────────────────────
    path("forgot-password/send-otp/",   ForgotPasswordSendOTPView.as_view(),   name="forgot-send-otp"),
    path("forgot-password/verify-otp/", ForgotPasswordVerifyOTPView.as_view(), name="forgot-verify-otp"),
    path("forgot-password/reset/",      ForgotPasswordResetView.as_view(),     name="forgot-reset"),
]