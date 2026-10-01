from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.mixins import ListModelMixin

from api.core.mixin import GenericDotsViewSet

from api.categories.models import Category

from api.categories.serializers import CategorySerializer


class CategoryViewset(GenericDotsViewSet, ListModelMixin):
    serializer_class = CategorySerializer
    queryset = Category.objects.all()
    permission_classes = [AllowAny]
