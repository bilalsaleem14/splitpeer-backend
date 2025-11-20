from django.db.models import Q
from django.contrib.auth import get_user_model

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from api.core.utils import DotsValidationError

from api.friends.models import Friend
from api.groups.models import Group, GroupMember

from api.users.serializers import UserSerializer


User = get_user_model()


class GroupSerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ["id", "created_by", "name", "description", "thumbnail", "members_count"]
    
    def get_members_count(self, obj):
        return obj.members.exclude(member=obj.created_by).count()


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


class GroupMemberSerializer(serializers.ModelSerializer):
    member = UserSerializer(read_only=True)
    
    class Meta:
        model = GroupMember
        fields = ["id", "group", "member", "created_at", "updated_at"]


class GroupMemberCreateSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=True)
    member = serializers.PrimaryKeyRelatedField(queryset=User.objects.all().exclude(is_staff=True, is_superuser=True), required=True)

    class Meta:
        model = GroupMember
        fields = ["group", "member"]
        validators = [
            UniqueTogetherValidator(queryset=GroupMember.objects.all(), fields=['group', 'member'], message="User is already a member of this group.")
        ]
    
    def validate(self, attrs):
        request = self.context["request"]
        group = attrs["group"]
        member = attrs["member"]
        
        if group.created_by != request.user:
            raise DotsValidationError({"error": "Only group creator can add members."})
        
        if GroupMember.objects.filter(group=group, member=member).exists():
            raise DotsValidationError({"error": "User is already a member of this group."})
        
        if member == group.created_by:
            raise DotsValidationError({"error": "Group creator is already a member."})
        
        if not Friend.objects.filter(created_by=request.user, member=member).exists():
            raise DotsValidationError({"error": "You can only add friends as group members."})
        
        return attrs
