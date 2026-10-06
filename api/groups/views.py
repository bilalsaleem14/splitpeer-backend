from django.http import Http404
from django.shortcuts import render
from django.db import transaction
from django.db.models import Q, Value, OuterRef, Subquery, When, IntegerField, Case
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.renderers import JSONRenderer, StaticHTMLRenderer

from django_filters.rest_framework import DjangoFilterBackend

from api.core.permissions import IsApprovedGroupMember, IsOwner
from api.core.filters import GroupMemberFilter, UserFilter
from api.core.mixin import DotsModelViewSet
from api.core.utils import DotsValidationError

from api.friends.models import Friend
from api.groups.models import Group, GroupMember

from api.users.serializers import ShortUserSerializer
from api.groups.serializers import GroupCreateSerializer, GroupJoinRequestSerializer, GroupJoinRespondSerializer, GroupMemberBulkCreateSerializer, GroupMemberCreateSerializer, GroupMemberSerializer, GroupSerializer

from api.groups.utils import annotate_group_queryset, create_group_member_activities, filter_by_approved_group_member


User = get_user_model()


class GroupViewSet(DotsModelViewSet):
    serializer_class = GroupSerializer
    serializer_create_class = GroupCreateSerializer
    queryset = Group.objects.all()
    permission_classes = [IsAuthenticated, IsOwner, IsApprovedGroupMember]
    permission_classes_by_action = {
        "default": [IsAuthenticated, IsOwner, IsApprovedGroupMember],
        "request_join": [IsAuthenticated],
        "respond_join_request": [AllowAny],
    }

    def get_queryset(self):
        queryset = super().get_queryset().filter(Q(created_by=self.request.user) | Q(members__user=self.request.user))
        return annotate_group_queryset(queryset).distinct().order_by("-id")

    def get_object(self):
        try:
            return super().get_object()
        except Http404:
            raise Http404("Group not found.")
    
    @action(detail=True, methods=["GET"], url_path="non-member-friends", serializer_class=ShortUserSerializer)
    def non_member_friends(self, request, pk=None):
        group = self.get_object()
        friend_qs = Friend.objects.filter(created_by=request.user)
        group_member_ids = group.members.values_list('user_id', flat=True)
        non_member_friend_ids = friend_qs.exclude(member_id__in=group_member_ids).values_list('member_id', flat=True)
        latest_friend_subquery = Friend.objects.filter(created_by=request.user, member_id=OuterRef('pk')).order_by('-id').values('id')[:1]
        non_member_friends = User.objects.filter(id__in=non_member_friend_ids).annotate(friend_record_id=Subquery(latest_friend_subquery)).order_by('-friend_record_id')

        filterset = UserFilter(request.GET, queryset=non_member_friends)
        filtered_queryset = filterset.qs.order_by('-friend_record_id')
        page = self.paginate_queryset(filtered_queryset)
        serializer = self.get_serializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)

    @action(detail=True, methods=["POST"], url_path="join-request", permission_classes=[IsAuthenticated], serializer_class=GroupMemberSerializer)
    def join_request(self, request, pk=None):
        group = self.get_object()
        serializer = GroupJoinRequestSerializer(data=request.data, context={"request": request, "group": group})
        serializer.is_valid(raise_exception=True)
        member = serializer.save()
        output_serializer = self.get_serializer(member, context=self.get_serializer_context())
        return Response({"message": "Request to join the group has been sent to the group creator.", "data": output_serializer.data}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["GET"], url_path="join-request/respond", permission_classes=[AllowAny], renderer_classes=[JSONRenderer, StaticHTMLRenderer])
    def respond_join_request(self, request):
        if request.method == "HEAD":
            return render(
                request,
                "email_templates/group_join_action_result.html",
                {"title": "Group Join Request", "callout": "Group Join Request", "message": "", "status_type": "info"},
                status=status.HTTP_200_OK,
            )

        serializer = GroupJoinRespondSerializer(data=request.query_params, context={"request": request})
        if not serializer.is_valid():
            error_context, error_status = GroupJoinRespondSerializer.get_error_response_data(serializer.errors)
            return render(request, "email_templates/group_join_action_result.html", error_context, status=error_status)

        result_context = serializer.save()
        return render(request, "email_templates/group_join_action_result.html", result_context, status=status.HTTP_200_OK)


class GroupMemberViewSet(DotsModelViewSet):
    serializer_class = GroupMemberSerializer
    serializer_create_class = GroupMemberCreateSerializer
    queryset = GroupMember.objects.all().select_related("user", "group").order_by("-id")
    permission_classes = [IsAuthenticated, IsApprovedGroupMember]
    filter_backends = [DjangoFilterBackend]
    filterset_class = GroupMemberFilter
    
    def get_queryset(self):
        queryset = filter_by_approved_group_member(super().get_queryset(), self.request, self.action)
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
