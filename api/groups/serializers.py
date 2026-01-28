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
        annotated_count = getattr(obj, "members_count_annotated", None)
        if annotated_count is not None:
            return annotated_count
        return obj.members.exclude(user=obj.created_by).count()

    def get_total_expenses(self, obj):
        annotated_total = getattr(obj, "total_expenses_annotated", None)
        if annotated_total is not None:
            return annotated_total
        total = obj.group_expenses.aggregate(total=Sum('amount'))['total']
        return total or 0.0
    
    def get_member_profile_pictures(self, obj):
        members = obj.members.exclude(user=obj.created_by)[:5]
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


class GroupMemberBulkCreateSerializer(serializers.Serializer):
    group = serializers.PrimaryKeyRelatedField(queryset=Group.objects.all(), required=True)
    user = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=User.objects.all().exclude(is_staff=True, is_superuser=True)), allow_empty=False)

    def validate(self, attrs):
        request = self.context["request"]
        group = attrs["group"]
        user_ids = [u.id for u in attrs["user"]]

        if group.created_by != request.user:
            raise DotsValidationError({"error": "Only group creator can add members."})

        existing_member_ids = set(GroupMember.objects.filter(group=group, user_id__in=user_ids).values_list("user_id", flat=True))
        friend_ids = set(Friend.objects.filter(created_by=request.user, member_id__in=user_ids).values_list("member_id", flat=True))

        errors = {}
        valid_user_ids = []

        for uid in user_ids:
            if uid == group.created_by.id:
                raise DotsValidationError({"error": "Group creator is already a member."})
            elif uid in existing_member_ids:
                raise DotsValidationError({"error": f"User {uid} is already a member of this group."})
            elif uid not in friend_ids:
                raise DotsValidationError({"error": f"You can only add friends as group members. User {uid} is not a friend."})
            else:
                valid_user_ids.append(uid)

        if errors:
            raise DotsValidationError(errors)

        attrs["valid_user_ids"] = valid_user_ids
        return attrs

    def create(self, validated_data):
        group = validated_data["group"]
        user_ids = validated_data["valid_user_ids"]
        instances = [GroupMember(group=group, user_id=uid) for uid in user_ids]
        return GroupMember.objects.bulk_create(instances)

