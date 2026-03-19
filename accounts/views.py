import random
import string
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.middleware import csrf
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .authentication import JWTAuthenticationFromCookie
from .models import PasswordResetOTP
from .serializers import AdminLoginSerializer


# ─────────────────────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────────────────────
OTP_EXPIRY_MINUTES = 5
OTP_LENGTH = 6


def _generate_otp():
    return "".join(random.choices(string.digits, k=OTP_LENGTH))


# ═════════════════════════════════════════════════════════════
# EXISTING AUTH VIEWS
# ═════════════════════════════════════════════════════════════

class AdminLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email    = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        user = authenticate(request, username=user_obj.username, password=password)
        if user is None:
            return Response(
                {"detail": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_superuser:
            return Response(
                {"detail": "Admin access only"},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh    = RefreshToken.for_user(user)
        access     = str(refresh.access_token)
        csrf_token = csrf.get_token(request)

        response = Response({"message": "Admin logged in successfully", "csrf": csrf_token})

        response.set_cookie(
            key=settings.JWT_ACCESS_COOKIE_NAME,
            value=access,
            httponly=True,
            secure=settings.JWT_ACCESS_COOKIE_SECURE,
            samesite=settings.JWT_ACCESS_COOKIE_SAMESITE,
            max_age=settings.JWT_ACCESS_COOKIE_MAX_AGE,
        )
        response.set_cookie(
            key=settings.JWT_REFRESH_COOKIE_NAME,
            value=str(refresh),
            httponly=True,
            secure=settings.JWT_REFRESH_COOKIE_SECURE,
            samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
            max_age=settings.JWT_REFRESH_COOKIE_MAX_AGE,
        )
        return response


class AdminLogoutView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass

        response = Response(
            {"message": "Admin logged out successfully"},
            status=status.HTTP_205_RESET_CONTENT,
        )
        response.delete_cookie(settings.JWT_ACCESS_COOKIE_NAME)
        response.delete_cookie(settings.JWT_REFRESH_COOKIE_NAME)
        return response


class AdminRefreshTokenView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
            if not refresh_token:
                return Response(
                    {"detail": "Refresh token missing"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )

            token      = RefreshToken(refresh_token)
            access     = str(token.access_token)
            csrf_token = csrf.get_token(request)

            response = Response({"message": "Access token refreshed", "csrf": csrf_token})
            response.set_cookie(
                key=settings.JWT_ACCESS_COOKIE_NAME,
                value=access,
                httponly=True,
                secure=settings.JWT_ACCESS_COOKIE_SECURE,
                samesite=settings.JWT_ACCESS_COOKIE_SAMESITE,
                max_age=settings.JWT_ACCESS_COOKIE_MAX_AGE,
            )
            return response

        except Exception:
            return Response(
                {"detail": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )


class AdminMeView(APIView):
    authentication_classes = [JWTAuthenticationFromCookie]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({"detail": "Admin access only"}, status=403)
        return Response({"email": request.user.email, "username": request.user.username})


# ═════════════════════════════════════════════════════════════
# FORGOT PASSWORD VIEWS
# ═════════════════════════════════════════════════════════════

class ForgotPasswordSendOTPView(APIView):
    """
    POST /api/admin/forgot-password/send-otp/
    Body: { "email": "admin@example.com" }
    Generates a 6-digit OTP, saves it (overwriting any previous one),
    and emails it to the admin.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get("email", "").strip().lower()

        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "No admin account found with this email."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user.is_superuser:
            return Response(
                {"detail": "No admin account found with this email."},
                status=status.HTTP_403_FORBIDDEN,
            )

        otp_code   = _generate_otp()
        expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)

        # Upsert — overwrite any existing OTP for this email
        PasswordResetOTP.objects.update_or_create(
            email=email,
            defaults={
                "otp":         otp_code,
                "expires_at":  expires_at,
                "is_verified": False,
            },
        )

        try:
            send_mail(
                subject="Your Admin Password Reset OTP",
                message=(
                    f"Hello {user.username},\n\n"
                    f"Your one-time password (OTP) for resetting your admin account password is:\n\n"
                    f"    {otp_code}\n\n"
                    f"This OTP is valid for {OTP_EXPIRY_MINUTES} minutes.\n"
                    f"If you did not request this, please ignore this email.\n\n"
                    f"— JRM / Apollo Admin"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception:
            PasswordResetOTP.objects.filter(email=email).delete()
            return Response(
                {"detail": "Failed to send OTP email. Please try again later."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"message": f"OTP sent to {email}. Valid for {OTP_EXPIRY_MINUTES} minutes."},
            status=status.HTTP_200_OK,
        )


class ForgotPasswordVerifyOTPView(APIView):
    """
    POST /api/admin/forgot-password/verify-otp/
    Body: { "email": "...", "otp": "123456" }
    Validates the OTP and marks it as verified so the reset step can proceed.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        otp   = request.data.get("otp", "").strip()

        if not email or not otp:
            return Response(
                {"detail": "Email and OTP are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            record = PasswordResetOTP.objects.get(email=email)
        except PasswordResetOTP.DoesNotExist:
            return Response(
                {"detail": "No OTP request found for this email."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if record.is_expired():
            record.delete()
            return Response(
                {"detail": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if record.otp != otp:
            return Response(
                {"detail": "Invalid OTP. Please try again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Mark verified so the reset step knows OTP was confirmed
        record.is_verified = True
        record.save(update_fields=["is_verified"])

        return Response(
            {"message": "OTP verified successfully."},
            status=status.HTTP_200_OK,
        )


class ForgotPasswordResetView(APIView):
    """
    POST /api/admin/forgot-password/reset/
    Body: { "email": "...", "otp": "123456", "new_password": "..." }
    Re-validates OTP + verified flag, sets new password, then DELETES the OTP record.
    """
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email        = request.data.get("email", "").strip().lower()
        otp          = request.data.get("otp", "").strip()
        new_password = request.data.get("new_password", "")

        if not email or not otp or not new_password:
            return Response(
                {"detail": "Email, OTP, and new password are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(new_password) < 6:
            return Response(
                {"detail": "Password must be at least 6 characters."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            record = PasswordResetOTP.objects.get(email=email)
        except PasswordResetOTP.DoesNotExist:
            return Response(
                {"detail": "No OTP request found. Please start again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if record.is_expired():
            record.delete()
            return Response(
                {"detail": "OTP has expired. Please request a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if record.otp != otp:
            return Response(
                {"detail": "OTP mismatch. Please start the process again."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not record.is_verified:
            return Response(
                {"detail": "OTP has not been verified yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        user.set_password(new_password)
        user.save()

        # ✅ Hard-delete the OTP — never reusable
        record.delete()

        return Response(
            {"message": "Password reset successfully. You can now log in."},
            status=status.HTTP_200_OK,
        )