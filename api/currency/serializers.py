from rest_framework import serializers
from api.currency.models import CurrencyDropDown


class CurrencyDropDownSerializer(serializers.ModelSerializer):
    class Meta:
        model = CurrencyDropDown
        fields = ["id", "fullname", "code", "symbol"]