from datetime import datetime

from django.contrib.auth import get_user_model

from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialLogin, SocialToken, SocialAccount

from api.core.utils import DotsValidationError

from api.jwtauth.serializers import UserSerializer


User = get_user_model()


class SocialLoginSerializer(serializers.Serializer):
    code = serializers.CharField(required=False, allow_blank=True)
    access_token = serializers.CharField(required=False, allow_blank=True)
    id_token = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not any([attrs.get("code"), attrs.get("access_token"), attrs.get("id_token")]):
            raise DotsValidationError({"error": "Provide access_token or id_token"})
        return attrs
    
    def validate_existing_user(self, attrs):
        try:            
            existing_user = User.objects.get(email__iexact=attrs.email)
            if not SocialAccount.objects.filter(user=existing_user).exists():
                raise DotsValidationError({"error": "An account already exists with this email address. Please sign in with your credentials."})
        except User.DoesNotExist:
            pass

    def save(self, adapter_class, request, callback_url="/"):
        data = self.validated_data
        # code = data.get("code")
        access_token = data.get("access_token")
        id_token = data.get("id_token")

        adapter = adapter_class(request)
        provider = adapter.get_provider()
        app = provider.app

        token = SocialToken(token=access_token or id_token, app=app)
        response_data = {"id_token": id_token} if id_token else {}

        
        try:
            login = adapter.complete_login(request, app, token, response=response_data)
            login.token = token
            login.state = SocialLogin.state_from_request(request)
        except Exception as e:
            raise DotsValidationError({"error": e})
        
        self.validate_existing_user(login.user)

        try:
            complete_social_login(request, login)
            user = login.user
            user.last_login = datetime.now()
            user.save(update_fields=["last_login"])
        except Exception as e:
            raise DotsValidationError({"error": e})
        return user

    def get_login_response(self, user):
        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user, context=self.context).data
        return {"refresh": str(refresh), "access": str(refresh.access_token), "user": user_data}
