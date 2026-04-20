from rest_framework import permissions


class IsAdminOrOwner(permissions.BasePermission):
    """Allow access only to admins or to the owner of the employee record."""

    message = "You do not have permission to access this employee record."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        return getattr(obj, 'user', None) == request.user
