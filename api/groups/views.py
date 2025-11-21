from django.db.models import Sum, Count, Q, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated

from django_filters.rest_framework import DjangoFilterBackend

from api.core.filters import GroupMemberFilter
from api.core.mixin import DotsModelViewSet
from api.core.utils import DotsValidationError

from api.groups.models import Group, GroupMember

from api.groups.serializers import GroupSerializer, GroupCreateSerializer, GroupMemberSerializer, GroupMemberCreateSerializer


User = get_user_model()


class GroupViewSet(DotsModelViewSet):
    serializer_class = GroupSerializer
    serializer_create_class = GroupCreateSerializer
    queryset = Group.objects.all().select_related("created_by").prefetch_related("members__user").annotate(members_count_annotated=Count("members", filter=~Q(members__user=F("created_by")), distinct=True), total_expenses_annotated=Coalesce(Sum("group_expenses__amount"), Value(0.0, output_field=DecimalField()))).order_by("-id")
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(created_by=self.request.user)


class GroupMemberViewSet(DotsModelViewSet):
    serializer_class = GroupMemberSerializer
    serializer_create_class = GroupMemberCreateSerializer
    queryset = GroupMember.objects.all().select_related("user", "group").order_by("-id")
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = GroupMemberFilter
    
    def get_queryset(self):
        queryset = super().get_queryset()
        return queryset.filter(group__members__user=self.request.user).distinct()
    
    def get_object(self):
        if self.request.method == "DELETE":
            return get_object_or_404(GroupMember.objects.select_related("user", "group"), pk=self.kwargs["pk"])
        return super().get_object()
    
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        group = instance.group
        
        if group.created_by != request.user:
            raise DotsValidationError({"error": "Only group creator can remove members."})
        
        if instance.user == group.created_by:
            raise DotsValidationError({"error": "Cannot remove group creator from the group."})
        
        instance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
