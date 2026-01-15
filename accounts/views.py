from urllib import response
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import authenticate
from django.middleware import csrf
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import AdminLoginSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .authentication import JWTAuthenticationFromCookie

from django.conf import settings


class AdminLoginView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = AdminLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        try:
            user_obj = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response(
                {"detail": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        user = authenticate(request, username=user_obj.username, password=password)
        if user is None:
            return Response(
                {"detail": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not user.is_superuser:
            return Response(
                {"detail": "Admin access only"},
                status=status.HTTP_403_FORBIDDEN
            )

        refresh = RefreshToken.for_user(user)
        access = str(refresh.access_token)
        csrf_token = csrf.get_token(request)

        # ✅ Store tokens in HttpOnly cookies
        response = Response({"message": "Admin logged in successfully", "csrf": csrf_token})

        # Access token
        response.set_cookie(
            key=settings.JWT_ACCESS_COOKIE_NAME,
            value=access,
            httponly=True,
            secure=settings.JWT_ACCESS_COOKIE_SECURE,
            samesite=settings.JWT_ACCESS_COOKIE_SAMESITE,
            max_age=settings.JWT_ACCESS_COOKIE_MAX_AGE,
        )

        # Refresh token
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
    authentication_classes = []  # correct
    permission_classes = []      # correct

    def post(self, request):
        refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass  # token already invalid

        response = Response(
            {"message": "Admin logged out successfully"},
            status=status.HTTP_205_RESET_CONTENT
        )

        response.delete_cookie(settings.JWT_ACCESS_COOKIE_NAME)
        response.delete_cookie(settings.JWT_REFRESH_COOKIE_NAME)

        return response
class AdminRefreshTokenView(APIView):
    """
    Refresh access token using HttpOnly refresh token cookie
    """
    authentication_classes = [JWTAuthentication]  # Optional
    permission_classes = []

    def post(self, request):
        try:
            # Read refresh token from cookie
            refresh_token = request.COOKIES.get(settings.JWT_REFRESH_COOKIE_NAME)
            if not refresh_token:
                return Response({"detail": "Refresh token missing"}, status=status.HTTP_401_UNAUTHORIZED)

            # Create new access token
            token = RefreshToken(refresh_token)
            access = str(token.access_token)

            # Issue new CSRF token
            csrf_token = csrf.get_token(request)

            # Set access token in HttpOnly cookie
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
            return Response({"detail": "Invalid or expired refresh token"}, status=status.HTTP_401_UNAUTHORIZED)

class AdminMeView(APIView):
    authentication_classes = [JWTAuthenticationFromCookie]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_superuser:
            return Response({"detail": "Admin access only"}, status=403)
        return Response({"email": request.user.email, "username": request.user.username})