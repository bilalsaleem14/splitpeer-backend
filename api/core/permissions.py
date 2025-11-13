from django.contrib.auth import get_user_model

from rest_framework import permissions


User = get_user_model()


class UserPermission(permissions.BasePermission):
    message = {"permission": ["You don't have permissions to perform this action."]}

    def has_permission(self, request, view):
        if not getattr(request.user, "role", False):
            return False
        if request.user.role in [User.Roles.USER]:
            return True
        return False


class IsOwner(permissions.BasePermission):
    message = {"permission": ["You don't have permissions to perform this action."]}

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if hasattr(obj, "created_by"):
            return obj.created_by == request.user
        if hasattr(obj, "created_for"):
            return obj.created_for == request.user
        return False
