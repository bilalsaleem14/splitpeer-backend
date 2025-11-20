from hmac import compare_digest
from datetime import timedelta

from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework.exceptions import AuthenticationFailed

from api.core.otp_helper import get_random_otp, send_confirmation_code, verify_otp
from api.core.utils import DotsValidationError
from api.core.validators import PasswordValidator
from api.core.profile_management import UserProfileOperations

from api.jwtauth.models import OTP

from api.users.serializers import UserSerializer


User = get_user_model()


class OTPSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True)
    otp_type = serializers.ChoiceField(choices=OTP.Type.choices, write_only=True)

    def validate(self, attrs):
        email = attrs["email"].lower()
        otp_type = attrs["otp_type"]
        user = User.objects.filter(email=email)
        
        if not user.exists() and otp_type == OTP.Type.FORGOT:
            raise DotsValidationError({"email": [f"This email is not registered"]})
        if user.exists() and otp_type in [OTP.Type.CREATE, OTP.Type.CHANGE]:
            raise DotsValidationError({"email": [f"User with this email already exists."]})
        
        timeout = timezone.now() + timedelta(seconds=300)
        new_otp = OTP.objects.create(code=get_random_otp(), email=email, type=otp_type, timeout=timeout)
        OTP.objects.filter(email=email, type=otp_type).exclude(pk=new_otp.pk).delete()
        # send_confirmation_code(new_otp=new_otp, otp_type=otp_type)
        return attrs


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True)
    otp_type = serializers.ChoiceField(choices=OTP.Type.choices, write_only=True)
    otp_code = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs["email"].lower()
        otp_code = attrs["otp_code"]
        otp_type = attrs["otp_type"]

        user_otp = OTP.objects.filter(email=email, type=otp_type).order_by("-pk").first()
        if not user_otp:
            raise DotsValidationError({"email": [f"OTP not found"]})
        if str(user_otp.code) != otp_code:
            raise DotsValidationError({"otp_code": ["Please enter a valid OTP Code"]})
        if user_otp.used:
            raise DotsValidationError({"otp_code": ["OTP is already used!"]})
        if timezone.now() > user_otp.timeout:
            raise DotsValidationError({"otp_code": ["Your OTP code is expired."]})
        
        user_otp.used = True
        user_otp.timeout = timezone.now() + timedelta(seconds=300)
        user_otp.save(update_fields=["used", "timeout"])
        return attrs


class UserCreateSerializer(serializers.ModelSerializer):
    confirm_password = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[PasswordValidator.validate_all])
    verification_token = serializers.CharField(required=True, write_only=True)

    class Meta:
        model = User
        fields = ["password", "confirm_password", "email", "verification_token", "fullname", "profile_picture"]

    def validate(self, attrs):
        password = attrs.get("password")
        confirm_password = attrs.pop("confirm_password", None)
        verification_token = attrs.get("verification_token", None)
        email = attrs.get("email").lower()

        if not compare_digest(password.encode('utf-8'), confirm_password.encode('utf-8')):
            raise serializers.ValidationError({"password": "Passwords do not match"})
        
        if not verification_token:
            raise serializers.ValidationError({"verification_token": "This field is required"}) 

        try:
            otp = OTP.objects.get(email=email, verification_token=verification_token, type=OTP.Type.CREATE)
        except OTP.DoesNotExist:
            raise DotsValidationError({"message": ["No record found, regenerate token!"]})
        verify_otp(user_otp=otp)
        return super().validate(attrs)

    def create(self, validated_data):
        validated_data.pop("verification_token")
        with transaction.atomic():
            user = super(UserCreateSerializer, self).create(validated_data)
            user.set_password(validated_data["password"])
            user.save(update_fields=["password"])
            return user


class UserUpdateSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["fullname", "profile_picture", "is_darkmode", "is_cloud_sync"]


class LoginSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        try:
            data = super().validate(attrs)
        except AuthenticationFailed:
            raise DotsValidationError({"detail": "No active account found with the given credentials"})

        serializer = UserSerializer(self.user, context=self.context)
        data.update(serializer.data)
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()

    def validate(self, attrs):
        self.token = attrs["refresh"]
        return attrs

    def save(self, **kwargs):
        try:
            RefreshToken(self.token).blacklist()
        except TokenError:
            raise DotsValidationError({"token": "Invalid token!"})


class PasswordResetSerializer(serializers.Serializer):
    confirm_password = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, required=True, validators=[PasswordValidator.validate_all])
    verification_token = serializers.CharField(required=True)

    def validate(self, attrs):
        password = attrs.get("password")
        confirm_password = attrs.get("confirm_password")

        if not compare_digest(password.encode('utf-8'), confirm_password.encode('utf-8')):
            raise serializers.ValidationError({"password": "Passwords do not match"})

        return attrs

    def set_password(self):
        UserProfileOperations.update_user_field(self.validated_data, field="password")
        return True


class UpdatePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True, error_messages={'blank': 'Password field cannot be empty.'})
    password = serializers.CharField(write_only=True, required=True, error_messages={'blank': 'Password field cannot be empty.'}, validators=[PasswordValidator.validate_all])
    confirm_password = serializers.CharField(required=True, error_messages={'blank': 'Password field cannot be empty.'})

    def validate(self, attrs):
        user = self.context["request"].user
        old_password = attrs["old_password"]
        password = attrs.get("password")
        confirm_password = attrs.pop("confirm_password", None)

        if not compare_digest(password.encode('utf-8'), confirm_password.encode('utf-8')):
            raise DotsValidationError({"password": "Password and Confirm Password do not match."})

        if not user.check_password(old_password):
            raise DotsValidationError({"old_password": ["Your current password is incorrect."]})
        
        if compare_digest(password.encode("utf-8"), old_password.encode("utf-8")):
            raise DotsValidationError({"password": "The new password cannot be the same as the old password."})

        return super().validate(attrs)

    def update_password(self, user):
        validated_data = self.validated_data
        user.set_password(validated_data["password"])
        user.save(update_fields=["password"])
        return True


class UpdateEmailSerializer(serializers.Serializer):
    verification_token = serializers.CharField(required=True)

    def set_email(self, user):
        UserProfileOperations.update_user_field(validated_data=self.validated_data, user=user, field="email")
        return True