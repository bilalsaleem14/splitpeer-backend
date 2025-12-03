from django.db import transaction
from django.db.models import Sum, Count, Q, F, Value, DecimalField, OuterRef, Subquery, When, IntegerField, Case
from django.db.models.functions import Coalesce
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated

from django_filters.rest_framework import DjangoFilterBackend

from api.core.permissions import IsOwner
from api.core.filters import GroupMemberFilter, UserFilter
from api.core.mixin import DotsModelViewSet
from api.core.utils import DotsValidationError

from api.friends.models import Friend
from api.groups.models import Group, GroupMember
from api.expenses.models import Expense

from api.users.serializers import ShortUserSerializer
from api.groups.serializers import GroupSerializer, GroupCreateSerializer, GroupMemberSerializer, GroupMemberCreateSerializer, GroupMemberBulkCreateSerializer

from api.groups.utils import create_group_member_activities


User = get_user_model()


class GroupViewSet(DotsModelViewSet):
    serializer_class = GroupSerializer
    serializer_create_class = GroupCreateSerializer
    queryset = Group.objects.all()
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        expenses_sum_subquery = Expense.objects.filter(group=OuterRef("pk")).values("group").annotate(total=Sum("amount")).values("total")
        return super().get_queryset().filter(Q(created_by=self.request.user) | Q(members__user=self.request.user)).select_related("created_by").prefetch_related("members__user").annotate(members_count_annotated=Count("members", filter=~Q(members__user=F("created_by")), distinct=True), total_expenses_annotated=Coalesce(Subquery(expenses_sum_subquery, output_field=DecimalField()), Value(0, output_field=DecimalField()))).distinct().order_by("-id")
    
    @action(detail=True, methods=["GET"], url_path="non-member-friends", serializer_class=ShortUserSerializer)
    def non_member_friends(self, request, pk=None):
        group = self.get_object()
        friends = Friend.objects.filter(created_by=request.user).values_list('member_id', flat=True)
        group_member_ids = group.members.values_list('user_id', flat=True)
        non_member_friend_ids = set(friends) - set(group_member_ids)
        non_member_friends = User.objects.filter(id__in=non_member_friend_ids)
        
        filterset = UserFilter(request.GET, queryset=non_member_friends)
        filtered_queryset = filterset.qs

        page = self.paginate_queryset(filtered_queryset)
        serializer = self.get_serializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)


class GroupMemberViewSet(DotsModelViewSet):
    serializer_class = GroupMemberSerializer
    serializer_create_class = GroupMemberCreateSerializer
    queryset = GroupMember.objects.all().select_related("user", "group").order_by("-id")
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend]
    filterset_class = GroupMemberFilter
    
    def get_queryset(self):
        queryset = super().get_queryset().filter(group__members__user=self.request.user).distinct()
        return queryset.annotate(is_request_user=Case(When(user=self.request.user, then=Value(0)), default=Value(1), output_field=IntegerField())).order_by("is_request_user", "-id")
    
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
    
    @action(detail=False, methods=["POST"], url_path="bulk-create", serializer_class=GroupMemberSerializer)
    def bulk_create(self, request):
        serializer = GroupMemberBulkCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            members = serializer.save()
            create_group_member_activities(members, request.user)
        output_serializer = self.serializer_class(members, many=True)
        return Response({"data": output_serializer.data}, status=status.HTTP_201_CREATED)
