from django.db.models import Q
from django.contrib.auth import get_user_model

from rest_framework import serializers

from api.core.utils import DotsValidationError

from api.groups.models import Group
from api.users.serializers import UserSerializer


User = get_user_model()


class GroupSerializer(serializers.ModelSerializer):

    class Meta:
        model = Group
        fields = ["id", "created_by", "name", "description", "thumbnail"]


class GroupCreateSerializer(serializers.ModelSerializer):

    class Meta:
        model = Group
        fields = ["name", "description", "thumbnail"]
    
    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        if self.context["request"].user != instance.created_by:
            raise DotsValidationError({"error": "You do not have permission to update this group."})
        return super().update(instance, validated_data)
