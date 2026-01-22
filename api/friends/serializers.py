from django.db.models import Q
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.conf import settings

from rest_framework import serializers

from api.core.utils import DotsValidationError, get_or_create_user_by_email
from api.core.otp_helper import send_invite_email
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
    email = serializers.EmailField(write_only=True, required=True)

    class Meta:
        model = Friend
        fields = ["email"]

    def validate_email(self, value):
        request = self.context.get('request')
        email = value.lower().strip()

        existing_user = User.objects.filter(email__iexact=email).first()

        if existing_user:
            if Friend.objects.filter(created_by=request.user, member=existing_user).exists():
                raise DotsValidationError({"error": "This user is already your friend."})

        if request.user.email.lower() == email:
            raise DotsValidationError({"error": "You cannot add yourself as your friend."})

        return email

    def create(self, validated_data):
        email = validated_data.pop('email')
        request = self.context["request"]

        user = get_or_create_user_by_email(email)
        friend = Friend.objects.create(created_by=request.user, member=user)

        send_invite_email(email, inviter=request.user)

        return friend


class UserWithFriendStatusSerializer(ShortUserSerializer):
    is_friend = serializers.BooleanField(read_only=True)

    class Meta(ShortUserSerializer.Meta):
        fields = ShortUserSerializer.Meta.fields + ["is_friend"]
