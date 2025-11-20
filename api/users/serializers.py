from django.contrib.auth import get_user_model

from rest_framework import serializers

from api.core.validators import validate_image


User = get_user_model()
    

class UserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["id", "email", "fullname", "profile_picture", "is_darkmode", "is_cloud_sync"]


class ImageSerializer(serializers.ModelSerializer):
    profile_picture = serializers.ImageField(validators=[validate_image()])
    
    class Meta:
        model = User
        fields = ["profile_picture"]


class ShortUserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["id", "email", "fullname", "profile_picture"]
