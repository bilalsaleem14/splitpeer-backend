from django.db.models import Sum, Count, Q, F, Value, DecimalField, OuterRef, Subquery
from django.db.models.functions import Coalesce
from django.contrib.auth import get_user_model

from rest_framework import filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from django_filters.rest_framework import DjangoFilterBackend

from api.core.mixin import DotsModelViewSet

from api.friends.models import Friend
from api.groups.models import Group
from api.expenses.models import Expense

from api.friends.serializers import FriendSerializer, FriendCreateSerializer, UserWithFriendStatusSerializer
from api.groups.serializers import GroupSerializer


User = get_user_model()


class FriendViewSet(DotsModelViewSet):
    serializer_class = FriendSerializer
    serializer_create_class = FriendCreateSerializer
    queryset = Friend.objects.all().select_related("member").order_by("-id")
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["member__fullname", "member__email"]

    def get_queryset(self):
        return super().get_queryset().filter(created_by=self.request.user)
        
    @action(detail=False, url_path="out", methods=["GET"], serializer_class=UserWithFriendStatusSerializer)
    def not_friend(self, request):
        user = request.user

        friend_ids = Friend.objects.filter(created_by=user).values_list("member_id", flat=True)
        users = User.objects.exclude(Q(id=user.id) | Q(id__in=friend_ids) | Q(is_staff=True) | Q(is_superuser=True)).order_by("-id")

        search = request.query_params.get("search")
        if search:
            users = users.filter(Q(fullname__icontains=search) | Q(email__icontains=search))

        page = self.paginate_queryset(users)
        serializer = self.get_serializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)
    
    @action(detail=True, methods=["GET"], url_path="groups", serializer_class=GroupSerializer)
    def common_groups(self, request, pk=None):
        friend = self.get_object()
        user = request.user
        expenses_sum_subquery = Expense.objects.filter(group=OuterRef("pk")).values("group").annotate(total=Sum("amount")).values("total")
        queryset = Group.objects.filter(members__user=user).filter(members__user=friend.member).select_related("created_by").prefetch_related("members__user").annotate(members_count_annotated=Count("members", filter=~Q(members__user=F("created_by")), distinct=True), total_expenses_annotated=Coalesce(Subquery(expenses_sum_subquery, output_field=DecimalField()), Value(0, output_field=DecimalField()))).order_by("-id")

        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)
