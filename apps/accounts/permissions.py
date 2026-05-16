from rest_framework import permissions

class IsCoach(permissions.BasePermission):
    """
    Allows access only to users with the COACH role.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == 'COACH')

class IsCoachOrReadOnly(permissions.BasePermission):
    """
    The request is authenticated as a user, but only coaches can modify.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return bool(request.user and request.user.is_authenticated and request.user.role == 'COACH')
