from django.contrib.auth import get_user_model

from rest_framework.permissions import IsAuthenticated

from api.core.mixin import GenericDotsViewSet, ListModelMixin

from api.activities.models import Activity
from api.activities.serializers import ActivitySerializer


User = get_user_model()


class ActivityViewset(GenericDotsViewSet, ListModelMixin):
    serializer_class = ActivitySerializer
    queryset = Activity.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(receiver=self.request.user).order_by('-id')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        un_read = queryset.filter(is_read=False)
        un_read.update(is_read=True)
        
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)
