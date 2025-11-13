from django.contrib.auth import get_user_model

from rest_framework.permissions import IsAuthenticated

from api.core.mixin import DotsModelViewSet

from api.groups.models import Group

from api.groups.serializers import GroupSerializer, GroupCreateSerializer


User = get_user_model()


class GroupViewSet(DotsModelViewSet):
    serializer_class = GroupSerializer
    serializer_create_class = GroupCreateSerializer
    queryset = Group.objects.all().select_related("created_by").order_by("-id")
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(created_by=self.request.user)
