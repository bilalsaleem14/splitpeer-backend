import requests
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile

from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from api.core.utils import DotsValidationError


User = get_user_model()


def extract_picture_url(extra):
    if isinstance(extra.get("picture"), str):
        return extra["picture"]

    return extra.get("picture", {}).get("data", {}).get("url")


class CustomSocialAdapter(DefaultSocialAccountAdapter):
    
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
