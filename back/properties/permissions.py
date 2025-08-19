from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner
        return obj.owner == request.user


class IsLandlord(permissions.BasePermission):
    """
    Permission for landlord-only actions.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type in ['landlord', 'company', 'admin']


class IsTenantOrLandlord(permissions.BasePermission):
    """
    Permission for tenant or landlord actions.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.user_type in ['tenant', 'landlord', 'company', 'admin']