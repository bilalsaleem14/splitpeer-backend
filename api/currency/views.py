from rest_framework.permissions import AllowAny, IsAdminUser

from api.core.mixin import DotsModelViewSet
from api.currency.models import CurrencyDropDown
from api.currency.serializers import CurrencyDropDownSerializer


class CurrencyDropDownViewSet(DotsModelViewSet):
    serializer_class = CurrencyDropDownSerializer
    queryset = CurrencyDropDown.objects.all().order_by("code")
    permission_classes = [AllowAny]
    permission_classes_by_action = {
        "default": [AllowAny],
        "create": [IsAdminUser],
        "update": [IsAdminUser],
        "partial_update": [IsAdminUser],
        "retrieve": [AllowAny],
        "destroy":[IsAdminUser],
        "list": [AllowAny],
    }