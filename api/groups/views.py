from django.db.models import Sum, Count
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated

from api.core.mixin import DotsModelViewSet
from api.core.utils import DotsValidationError

from api.groups.models import Group, GroupMember

from api.groups.serializers import GroupSerializer, GroupCreateSerializer, GroupMemberSerializer, GroupMemberCreateSerializer


User = get_user_model()


class GroupViewSet(DotsModelViewSet):
    serializer_class = GroupSerializer
    serializer_create_class = GroupCreateSerializer
    queryset = Group.objects.all().select_related("created_by").annotate(members_count_annotated=Count("members", distinct=True), total_expenses_annotated=Sum("group_expenses__amount")).order_by("-id")
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(created_by=self.request.user)
    
    def get_group(self):
        return self.get_object()


class GroupMemberViewSet(DotsModelViewSet):
    serializer_class = GroupMemberSerializer
    serializer_create_class = GroupMemberCreateSerializer
    queryset = GroupMember.objects.all().select_related("user", "group").order_by("-id")
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        group_id = self.request.query_params.get("group", None)
        return super().get_queryset().filter(group_id=group_id)
    
    def get_object(self):
        if self.request.method == "DELETE":
            return get_object_or_404(GroupMember.objects.select_related("user", "group"), pk=self.kwargs["pk"])
        return super().get_object()
    
    def get_group(self):
        group_id = self.request.query_params.get("group")
        try:
            return Group.objects.get(id=group_id, created_by=self.request.user)
        except Group.DoesNotExist:
            raise DotsValidationError({"error": "Group not found."})
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        group = instance.group
        
        if group.created_by != request.user:
            raise DotsValidationError({"error": "Only group creator can remove members."})
        
        if instance.user == group.created_by:
            raise DotsValidationError({"error": "Cannot remove group creator from the group."})
        
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
