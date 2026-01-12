# accounts/authentication.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings

class JWTAuthenticationFromCookie(JWTAuthentication):
    def authenticate(self, request):
        access_token = request.COOKIES.get(settings.JWT_ACCESS_COOKIE_NAME)
        if access_token is None:
            return None

        # Temporarily add token to headers for parent class
        request.META['HTTP_AUTHORIZATION'] = f'Bearer {access_token}'
        return super().authenticate(request)
