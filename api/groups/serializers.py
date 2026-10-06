from django.conf import settings
from django.core import signing
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.utils import timezone

from rest_framework import serializers, status
from rest_framework.validators import UniqueTogetherValidator

from api.core.otp_helper import send_group_join_request_email, send_group_join_response_email
from api.core.utils import DotsValidationError
from api.core.validators import validate_image

from api.friends.models import Friend
from api.groups.models import Group, GroupMember
from api.groups.utils import build_group_join_action_urls, get_user_group_membership, verify_group_join_token
from api.currency.models import CurrencyDropDown

from api.users.serializers import ShortUserSerializer, ImageSerializer
from api.currency.serializers import CurrencyDropDownSerializer


User = get_user_model()


class GroupSerializer(serializers.ModelSerializer):
    members_count = serializers.SerializerMethodField()
    total_expenses = serializers.SerializerMethodField()
    member_profile_pictures = serializers.SerializerMethodField()
    currency = CurrencyDropDownSerializer(read_only=True)
    membership_status = serializers.SerializerMethodField()
    can_request_join = serializers.SerializerMethodField()

    class Meta:
        model = Group
        fields = ["id", "created_by", "name", "description", "thumbnail", "currency", "members_count", "total_expenses", "member_profile_pictures", "membership_status", "can_request_join"]
    
    def validate_currency(self, value):
        if not CurrencyDropDown.objects.filter(code=value).exists():
            raise serializers.ValidationError("Unsupported currency")
        return value

    def get_membership_status(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None
        if obj.created_by_id == user.id:
            return GroupMember.Status.APPROVED
        member = get_user_group_membership(obj, user)
        return member.status if member else None

    def get_can_request_join(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated or obj.created_by_id == user.id:
            return False
        member = get_user_group_membership(obj, user)
        return member.can_request_join() if member else False

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
    currency = serializers.CharField(write_only=True)

    class Meta:
        model = Group
        fields = ["name", "description", "thumbnail", "currency"]

    def validate_currency(self, value):
        try:
            return CurrencyDropDown.objects.get(code=value)
        except CurrencyDropDown.DoesNotExist:
            raise serializers.ValidationError("Unsupported currency")

    def create(self, validated_data):
        currency = validated_data.pop("currency")

        validated_data["currency"] = currency
        validated_data["created_by"] = self.context["request"].user

        return super().create(validated_data)

    def update(self, instance, validated_data):
        if self.context["request"].user != instance.created_by:
            raise DotsValidationError({"error": "You do not have permission to update this group."})

        if "currency" in validated_data:
            raise DotsValidationError({"error": "Group currency cannot be updated."})

        return super().update(instance, validated_data)


class GroupMemberSerializer(serializers.ModelSerializer):
    user = ShortUserSerializer(read_only=True)
    
    class Meta:
        model = GroupMember
        fields = ["id", "group", "user", "status", "last_requested_at", "responded_at", "created_at", "updated_at"]


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


class GroupJoinRequestSerializer(serializers.Serializer):
    
    def validate(self, attrs):
        request = self.context["request"]
        group = self.context["group"]

        if group.created_by_id == request.user.id:
            raise DotsValidationError({"error": "You already have access to this group."})

        member = get_user_group_membership(group, request.user)
        if not member:
            raise DotsValidationError({"error": "You are not a member of this group."})

        if member.status == GroupMember.Status.APPROVED:
            raise DotsValidationError({"error": "Your membership in this group is already approved."})

        if not member.can_request_join():
            raise DotsValidationError({"error": "A join request is already pending approval from the group creator."})

        attrs["member"] = member
        return attrs

    def save(self, **kwargs):
        request = self.context["request"]
        group = self.context["group"]
        member = self.validated_data["member"]

        member.status = GroupMember.Status.PENDING
        member.last_requested_at = timezone.now()
        member.save(update_fields=["status", "last_requested_at", "updated_at"])

        approve_url, reject_url = build_group_join_action_urls(request, member)
        send_group_join_request_email(creator=group.created_by, requester=request.user, group=group, approve_url=approve_url, reject_url=reject_url)
        return member


class GroupJoinRespondSerializer(serializers.Serializer):
    token = serializers.CharField(required=True, error_messages={"required": "Missing join request token.", "blank": "Missing join request token."})

    def validate_token(self, value):
        max_age = getattr(settings, "GROUP_JOIN_TOKEN_MAX_AGE_SECONDS", None)
        try:
            payload = verify_group_join_token(value, max_age=max_age)
        except signing.SignatureExpired:
            raise serializers.ValidationError("This join request link has expired.", code="expired")
        except signing.BadSignature:
            raise serializers.ValidationError("This join request link is invalid.", code="invalid")

        if payload.get("action") not in ("approve", "reject"):
            raise serializers.ValidationError("Unsupported action in join request link.", code="invalid_action")

        return payload

    def validate(self, attrs):
        payload = attrs["token"]
        member = GroupMember.objects.select_related("group__created_by", "user").filter(id=payload.get("member_id"), group_id=payload.get("group_id")).first()

        if not member:
            raise serializers.ValidationError({"member": "The group or member associated with this request no longer exists."}, code="not_found")

        attrs["member"] = member
        attrs["decision"] = payload["action"]
        return attrs

    def save(self, **kwargs):
        member = self.validated_data["member"]
        decision = self.validated_data["decision"]
        group = member.group
        requester = member.user
        creator = group.created_by

        if member.status != GroupMember.Status.PENDING:
            if member.status == GroupMember.Status.APPROVED:
                callout = f"Already Approved — {group.name}"
                msg = f"{requester.fullname} has already been approved to access '{group.name}'."
            elif member.status == GroupMember.Status.REJECTED:
                callout = f"Already Declined — {group.name}"
                msg = f"This join request for {requester.fullname} in '{group.name}' has already been declined."
            else:
                callout = f"No Pending Request — {group.name}"
                msg = f"There is no pending join request from {requester.fullname} for '{group.name}'."
            return {
                "title": "Request Already Processed",
                "creator_name": creator.fullname,
                "callout": callout,
                "message": msg,
                "status_type": member.status,
            }

        is_approved = decision == "approve"
        member.status = GroupMember.Status.APPROVED if is_approved else GroupMember.Status.REJECTED
        member.responded_at = timezone.now()
        member.save(update_fields=["status", "responded_at", "updated_at"])

        send_group_join_response_email(member_user=requester, creator=creator, group=group, is_approved=is_approved)

        if is_approved:
            return {
                "title": "Request Approved",
                "creator_name": creator.fullname,
                "callout": f"Access Granted — {group.name}",
                "message": f"You have approved {requester.fullname}'s request to join '{group.name}'. They have been notified by email and now have access to the group.",
                "status_type": member.status,
            }

        return {
            "title": "Request Rejected",
            "creator_name": creator.fullname,
            "callout": f"Request Declined — {group.name}",
            "message": f"You have declined {requester.fullname}'s request to join '{group.name}'. They have been notified by email.",
            "status_type": member.status,
        }

    @staticmethod
    def get_error_response_data(errors):
        if "member" in errors:
            msg = str(errors["member"][0])
            return {"title": "Request Not Found", "callout": "Request Not Found", "message": msg, "status_type": "info"}, status.HTTP_404_NOT_FOUND

        token_errors = errors.get("token", ["Invalid join request link."])
        first_error = token_errors[0]
        code = getattr(first_error, "code", "")
        title_map = {
            "expired": "Link Expired",
            "invalid": "Invalid Link",
            "invalid_action": "Invalid Action",
        }
        title = title_map.get(code, "Invalid Request")
        return {"title": title, "callout": title, "message": str(first_error), "status_type": "info"}, status.HTTP_400_BAD_REQUEST
