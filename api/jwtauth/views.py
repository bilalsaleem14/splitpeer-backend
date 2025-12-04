from django.utils import timezone
from django.contrib.auth import get_user_model

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from api.core.mixin import GenericDotsViewSet, UpdateDotsModelMixin
from api.jwtauth.models import OTP

from api.jwtauth.serializers import OTPSerializer, VerifyOTPSerializer, UserCreateSerializer, UserUpdateSerializer, LoginSerializer, LogoutSerializer, PasswordResetSerializer, UpdatePasswordSerializer, UpdateEmailSerializer
from api.users.serializers import ImageSerializer, UserSerializer


User = get_user_model()


class OTPViewSet(GenericDotsViewSet):
    serializer_class = OTPSerializer
    queryset = OTP.objects.all()
    permission_classes = [AllowAny]

    @action(detail=False, methods=["POST"], url_path="send", serializer_class=OTPSerializer)
    def generate_otp(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(data={"otp": ["OTP sent successfully"]})

    @action(detail=False, methods=["PATCH"], url_path="verify", serializer_class=VerifyOTPSerializer)
    def verify_otp(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        otp_type = serializer.validated_data["otp_type"]

        user_otp = OTP.objects.filter(email=email, type=otp_type).order_by("-pk").first()
        return Response({"verification_token": [user_otp.verification_token]})


class RegistrationViewSet(GenericDotsViewSet):
    serializer_class = UserSerializer
    serializer_create_class = UserCreateSerializer
    permission_classes = [AllowAny]

    def get_serializer_create(self, *args, **kwargs):
        serializer = self.get_serializer_create_class()
        kwargs["context"] = self.get_serializer_context()
        return serializer(*args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer_create(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        data = self.get_serializer(instance=user).data
        refresh = RefreshToken.for_user(user)
        user_data = {**data, "refresh": str(refresh), "access": str(refresh.access_token)}
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        return Response(user_data, status=status.HTTP_201_CREATED)


class LoginViewset(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=LogoutSerializer,
        responses={
            status.HTTP_200_OK: openapi.Response(description="Logout successful"),
            status.HTTP_400_BAD_REQUEST: openapi.Response(description="Invalid data"),
            status.HTTP_401_UNAUTHORIZED: openapi.Response(description="Unauthorized user"),
        },
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(status=status.HTTP_200_OK)


class ProfileViewSets(GenericDotsViewSet):
    permission_classes = [IsAuthenticated]
    pagination_class = None
    filter_backends = None

    @action(detail=False, url_path="password/reset", methods=["PATCH"], permission_classes=[AllowAny], serializer_class=PasswordResetSerializer)
    def reset(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.set_password()
        return Response({"user": ["Password has been reset successfully"]}, status=status.HTTP_200_OK)

    @action(detail=False, url_path="password/update", methods=["PATCH"], serializer_class=UpdatePasswordSerializer)
    def update_password(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.update_password(request.user)
        return Response({"user": ["Password has been updated successfully"]}, status=status.HTTP_200_OK)
    
    @action(detail=False, url_path="email/update", methods=["PATCH"], serializer_class=UpdateEmailSerializer, permission_classes=[IsAuthenticated])
    def update_email(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.set_email(request.user)
        return Response({"email": ["Email has been updated successfully"]}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["GET"], url_path="me", serializer_class=UserSerializer)
    def me(self, request, *args, **kwargs):
        user = request.user
        serializer = self.get_serializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class UserProfileViewset(GenericDotsViewSet, UpdateDotsModelMixin):
    serializer_class = UserSerializer
    serializer_create_class = UserUpdateSerializer
    queryset = User.objects.all()
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_create_class(self):
        user = self.request.user
        if user.is_anonymous:
            return serializers.Serializer
        return self.serializer_create_class

    def get_serializer_create(self, *args, **kwargs):
        serializer = self.get_serializer_create_class()
        kwargs["context"] = self.get_serializer_context()
        return serializer(*args, **kwargs)

    @swagger_auto_schema(request_body=openapi.Schema(type=openapi.TYPE_OBJECT, required=["image"], properties={"image": openapi.Schema(type=openapi.TYPE_FILE)}))
    def user_image(self, request, *args, **kwargs):
        serializer = ImageSerializer(data=request.data, partial=True, instance=request.user, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"data": [serializer.data]}, status=status.HTTP_200_OK)
