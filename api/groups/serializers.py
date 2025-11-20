from django.db.models import Sum
from django.contrib.auth import get_user_model

from rest_framework import serializers
from rest_framework.validators import UniqueTogetherValidator

from api.core.utils import DotsValidationError
from api.core.validators import validate_image

from api.friends.models import Friend
from api.groups.models import Group, GroupMember

from api.users.serializers import ShortUserSerializer, ImageSerializer


User = get_user_model()


class GroupSerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    total_expenses = serializers.SerializerMethodField()
    member_profile_pictures = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ["id", "created_by", "name", "description", "thumbnail", "members_count", "total_expenses", "member_profile_pictures"]
    
    def get_members_count(self, obj):
        return getattr(obj, "members_count_annotated", 0)

    def get_total_expenses(self, obj):
        return getattr(obj, "total_expenses_annotated", 0)
    
    def get_member_profile_pictures(self, obj):
        members = obj.members.all()[:5]
        users = [m.user for m in members]
        return ImageSerializer(users, many=True, context=self.context).data


class GroupCreateSerializer(serializers.ModelSerializer):
    thumbnail = serializers.ImageField(validators=[validate_image()])

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
    user = ShortUserSerializer(read_only=True)
    
    class Meta:
        model = GroupMember
        fields = ["id", "group", "user", "created_at", "updated_at"]


class GroupMemberCreateSerializer(serializers.ModelSerializer):
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=True)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all().exclude(is_staff=True, is_superuser=True), required=True)

    class Meta:
        model = GroupMember
        fields = ["group", "user"]
        validators = [
            UniqueTogetherValidator(queryset=GroupMember.objects.all(), fields=['group', 'user'], message="User is already a member of this group.")
        ]
    
    def validate(self, attrs):
        request = self.context["request"]
        group = attrs["group"]
        user = attrs["user"]
        
        if group.created_by != request.user:
            raise DotsValidationError({"error": "Only group creator can add members."})
        
        if GroupMember.objects.filter(group=group, user=user).exists():
            raise DotsValidationError({"error": "User is already a member of this group."})
        
        if user == group.created_by:
            raise DotsValidationError({"error": "Group creator is already a member."})
        
        if not Friend.objects.filter(created_by=request.user, member=user).exists():
            raise DotsValidationError({"error": "You can only add friends as group members."})
        
        return attrs
