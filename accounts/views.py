import random
import string
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.middleware import csrf
from django.utils import timezone

from employee.models import Employee

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

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


# ✅ BLACKLIST ALL TOKENS (IMPORTANT)
def blacklist_user_tokens(user):
    try:
        tokens = OutstandingToken.objects.filter(user=user)
        for token in tokens:
            BlacklistedToken.objects.get_or_create(token=token)
    except Exception:
        pass


# ═════════════════════════════════════════════════════════════
# AUTH VIEWS
# ═════════════════════════════════════════════════════════════

class LoginView(APIView):
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
            return Response({"detail": "Invalid email or password"}, status=401)

        user = authenticate(request, username=user_obj.username, password=password)
        if user is None:
            return Response({"detail": "Invalid email or password"}, status=401)

        if not user.is_active:
            return Response({"detail": "Account is disabled."}, status=403)

        role = "admin"
        employee = None
        if not user.is_superuser:
            try:
                employee = user.employee_profile
            except Employee.DoesNotExist:
                return Response(
                    {"detail": "Employee account not linked. Contact administrator."},
                    status=403,
                )
            role = "employee"

        blacklist_user_tokens(user)

        refresh = RefreshToken.for_user(user)
        access  = str(refresh.access_token)
        csrf_token = csrf.get_token(request)

        response_data = {
            "message": "Login successful",
            "csrf": csrf_token,
            "role": role,
        }

        if employee is not None:
            response_data["employee_id"] = employee.employee_id
            if employee.is_temp_password:
                response_data["force_password_change"] = True

        response = Response(response_data)

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
    authentication_classes = [JWTAuthenticationFromCookie]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # ✅ Logout from ALL devices
        blacklist_user_tokens(request.user)

        response = Response(
            {"message": "Logged out from all devices"},
            status=status.HTTP_205_RESET_CONTENT,
        )

        response.delete_cookie(settings.JWT_ACCESS_COOKIE_NAME)
        response.delete_cookie(settings.JWT_REFRESH_COOKIE_NAME)

        return response


class AdminRefreshTokenView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)

        if not refresh_token:
            return Response({"detail": "Refresh token missing"}, status=401)

        try:
            old_token = RefreshToken(refresh_token)

            # ✅ Blacklist old token BEFORE generating new one
            old_token.blacklist()

            # ✅ Get user from token's payload, not .user attribute
            user_id = old_token["user_id"]
            user = User.objects.get(id=user_id)

            # ✅ Generate fresh token pair
            new_token = RefreshToken.for_user(user)
            access = str(new_token.access_token)
            csrf_token = csrf.get_token(request)

            response = Response({
                "message": "Token refreshed",
                "csrf": csrf_token
            })

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
                value=str(new_token),
                httponly=True,
                secure=settings.JWT_REFRESH_COOKIE_SECURE,
                samesite=settings.JWT_REFRESH_COOKIE_SAMESITE,
                max_age=settings.JWT_REFRESH_COOKIE_MAX_AGE,
            )

            return response

        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=401)
        except Exception as e:
            return Response({"detail": "Invalid or expired refresh token"}, status=401)
        
class CheckAuthView(APIView):
    authentication_classes = [JWTAuthenticationFromCookie]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = {
            "email": request.user.email,
            "username": request.user.username,
            "is_superuser": request.user.is_superuser,
        }

        if request.user.is_superuser:
            data["role"] = "admin"
        else:
            try:
                employee = request.user.employee_profile
                data["role"] = "employee"
                data["employee_id"] = employee.employee_id
                data["employee_name"] = employee.full_name
            except Employee.DoesNotExist:
                return Response(
                    {"detail": "Employee account not linked. Contact administrator."},
                    status=403,
                )

        return Response(data)


# ═════════════════════════════════════════════════════════════
# FORGOT PASSWORD (UNCHANGED - ALREADY GOOD)
# ═════════════════════════════════════════════════════════════

class ForgotPasswordSendOTPView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get("email", "").strip().lower()

        if not email:
            return Response({"detail": "Email is required."}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "No admin account found"}, status=404)

        if not user.is_superuser:
            return Response({"detail": "No admin account found"}, status=403)

        otp_code   = _generate_otp()
        expires_at = timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES)

        PasswordResetOTP.objects.update_or_create(
            email=email,
            defaults={
                "otp": otp_code,
                "expires_at": expires_at,
                "is_verified": False,
            },
        )

        try:
            send_mail(
                subject="Your Admin Password Reset OTP",
                message=f"Your OTP is {otp_code}. Valid for {OTP_EXPIRY_MINUTES} minutes.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception:
            PasswordResetOTP.objects.filter(email=email).delete()
            return Response({"detail": "Failed to send OTP"}, status=500)

        return Response({"message": "OTP sent"}, status=200)


class ForgotPasswordVerifyOTPView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        otp   = request.data.get("otp", "").strip()

        if not email or not otp:
            return Response({"detail": "Email and OTP required"}, status=400)

        try:
            record = PasswordResetOTP.objects.get(email=email)
        except PasswordResetOTP.DoesNotExist:
            return Response({"detail": "No OTP request found"}, status=400)

        if record.is_expired():
            record.delete()
            return Response({"detail": "OTP expired"}, status=400)

        if record.otp != otp:
            return Response({"detail": "Invalid OTP"}, status=400)

        record.is_verified = True
        record.save(update_fields=["is_verified"])

        return Response({"message": "OTP verified"}, status=200)


class ForgotPasswordResetView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        email = request.data.get("email", "").strip().lower()
        otp = request.data.get("otp", "").strip()
        new_password = request.data.get("new_password", "")

        if not email or not otp or not new_password:
            return Response({"detail": "All fields required"}, status=400)

        if len(new_password) < 6:
            return Response({"detail": "Password too short"}, status=400)

        try:
            record = PasswordResetOTP.objects.get(email=email)
        except PasswordResetOTP.DoesNotExist:
            return Response({"detail": "No OTP request found"}, status=400)

        if record.is_expired():
            record.delete()
            return Response({"detail": "OTP expired"}, status=400)

        if record.otp != otp or not record.is_verified:
            return Response({"detail": "Invalid or unverified OTP"}, status=400)

        user = User.objects.get(email=email)
        user.set_password(new_password)
        user.save()

        record.delete()

        return Response({"message": "Password reset successful"}, status=200)
    
from .models import EmailConfig
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.response import Response
from rest_framework import status
from .authentication import JWTAuthenticationFromCookie


@api_view(['POST'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def save_email_config(request):
    """Frontend sends email credentials here to save to DB."""
    data = request.data

    required = ['email_host_user', 'email_host_password']
    for field in required:
        if not data.get(field):
            return Response({"error": f"{field} is required"}, status=400)

    config, created = EmailConfig.objects.update_or_create(
        # singleton: always update the first/only row
        id=1,
        defaults={
            'email_host':          data.get('email_host', 'smtp.gmail.com'),
            'email_port':          int(data.get('email_port', 587)),
            'email_use_tls':       data.get('email_use_tls', True),
            'email_host_user':     data['email_host_user'],
            'email_host_password': data['email_host_password'],
        }
    )

    return Response({
        "success": True,
        "message": "Email configuration saved.",
        "created": created
    }, status=201 if created else 200)


@api_view(['GET'])
@authentication_classes([JWTAuthenticationFromCookie])
@permission_classes([IsAuthenticated])
def get_email_config(request):
    """Return current config (hide password)."""
    try:
        config = EmailConfig.objects.latest('updated_at')
        return Response({
            "email_host":      config.email_host,
            "email_port":      config.email_port,
            "email_use_tls":   config.email_use_tls,
            "email_host_user": config.email_host_user,
            "password_set":    bool(config.email_host_password),  # never expose password
        })
    except EmailConfig.DoesNotExist:
        return Response({"detail": "No config found"}, status=404) 
    
