from django.db.models import Q, Exists, OuterRef
from django.contrib.auth import get_user_model

from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import filters
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action

from api.core.mixin import DotsModelViewSet

from api.friends.models import Friend

from api.friends.serializers import FriendSerializer, FriendCreateSerializer, UserWithFriendStatusSerializer


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

        # friend_qs = Friend.objects.filter(created_by=user, member_id=OuterRef("id"))
        friend_ids = Friend.objects.filter(created_by=user).values_list("member_id", flat=True)
        users = User.objects.exclude(Q(id=user.id) | Q(id__in=friend_ids) | Q(is_staff=True) | Q(is_superuser=True)).order_by("-id")
        # users = users.annotate(is_friend=Exists(friend_qs))

        search = request.query_params.get("search")
        if search:
            users = users.filter(Q(fullname__icontains=search) | Q(email__icontains=search))

        page = self.paginate_queryset(users)
        serializer = self.get_serializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)
