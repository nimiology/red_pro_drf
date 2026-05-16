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

class IsOwnerOrCoachReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    Coaches can read if the athlete is in their squad.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            if obj.athlete == request.user:
                return True
            if request.user.role == 'COACH':
                return obj.athlete.squads.filter(coach=request.user).exists()
            return False
        
        # Write permissions are only allowed to the owner.
        return obj.athlete == request.user
