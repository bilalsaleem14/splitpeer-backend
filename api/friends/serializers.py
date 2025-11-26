from django.db.models import Q
from django.contrib.auth import get_user_model

from rest_framework import serializers

from api.core.utils import DotsValidationError

from api.friends.models import Friend
from api.users.serializers import ShortUserSerializer


User = get_user_model()


class FriendSerializer(serializers.ModelSerializer):
    member = ShortUserSerializer(read_only=True)

    class Meta:
        model = Friend
        fields = ["id", "created_by", "member"]
        read_only_fields = ["id", "created_at", "member"]


class FriendCreateSerializer(serializers.ModelSerializer):
    member = serializers.PrimaryKeyRelatedField(queryset=User.objects.exclude(Q(is_staff=True) | Q(is_superuser=True)), required=True)

    class Meta:
        model = Friend
        fields = ["member"]
    
    def validate(self, attrs):
        request = self.context.get('request')
        member = attrs['member']
        
        if request.user == member:
            raise DotsValidationError({"error": "You cannot add yourself as your friend."})
        
        if Friend.objects.filter(created_by=request.user, member=member).exists():
            raise DotsValidationError({"error": "This user is already your friend."})
        
        return attrs
    
    def create(self, validated_data):
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class UserWithFriendStatusSerializer(ShortUserSerializer):
    is_friend = serializers.BooleanField(read_only=True)

    class Meta(ShortUserSerializer.Meta):
        fields = ShortUserSerializer.Meta.fields + ["is_friend"]
