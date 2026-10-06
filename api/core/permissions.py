from django.contrib.auth import get_user_model

from rest_framework import permissions

from api.groups.models import Group, GroupMember
from api.groups.utils import is_approved_group_member


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


class IsApprovedGroupMember(permissions.BasePermission):
    message = {"error": "Group admin's approval is required to join and view the group information and members. Please send a request to join the group."}

    def has_permission(self, request, view):
        group_id = request.query_params.get("group")
        if group_id and str(group_id).isdigit():
            group = Group.objects.prefetch_related("members").filter(pk=group_id, members__user=request.user).first()
            if group and not is_approved_group_member(group, request.user):
                return False
        elif getattr(view, "action", None) in ("list", "list_dropdown") and getattr(view, "basename", None) in ("expenses", "group_members"):
            user_memberships = GroupMember.objects.filter(user=request.user)
            if user_memberships.exists() and not user_memberships.filter(status=GroupMember.Status.APPROVED).exists():
                return False
        return True

    def has_object_permission(self, request, view, obj):
        group = obj if hasattr(obj, "members") else getattr(obj, "group", None)
        if group is None:
            return True
        return is_approved_group_member(group, request.user)
