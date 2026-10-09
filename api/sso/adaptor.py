import requests

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Error

from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from api.core.utils import DotsValidationError


User = get_user_model()


def extract_picture_url(extra):
    if isinstance(extra.get("picture"), str):
        return extra["picture"]

    return extra.get("picture", {}).get("data", {}).get("url")


class CustomSocialAdapter(DefaultSocialAccountAdapter):

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        fullname = (data.get("name") or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or "social user")
        user.fullname = fullname
        return user
    
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        try:
            social_account = SocialAccount.objects.get(user=user)
            user.fullname = social_account.extra_data.get("name", "")
            profile_picture = None
            profile_picture = extract_picture_url(social_account.extra_data)
            if profile_picture:
                response = requests.get(profile_picture)
                if response.status_code == 200:
                    user.profile_picture.save(f"{user.fullname}_picture.jpg", ContentFile(response.content), save=True)
        except Exception:
            raise DotsValidationError({"error": "Failed to save extra details."})
        
        user.save()
        return user


class MultiClientGoogleAdapter(GoogleOAuth2Adapter):
    def complete_login(self, request, app, token, response, **kwargs):
        raw_id_token = (response or {}).get("id_token")
        if not raw_id_token:
            # access_token path: falls back to the userinfo endpoint (FETCH_USERINFO)
            return super().complete_login(request, app, token, response, **kwargs)

        try:
            # Verifies signature, expiry and issuer against Google's certs
            idinfo = google_id_token.verify_oauth2_token(raw_id_token, google_requests.Request(), audience=None)
        except ValueError as e:
            raise OAuth2Error(f"Invalid id_token: {e}") from e

        if idinfo.get("aud") not in settings.GOOGLE_CLIENT_IDS:
            raise OAuth2Error("Invalid id_token audience")

        return self.get_provider().sociallogin_from_response(request, idinfo)
