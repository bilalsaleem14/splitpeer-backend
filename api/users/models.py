from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

from api.core.models import CharFieldSizes


class UserManager(BaseUserManager):

    def normalize_email(self, email):
        email = super().normalize_email(email)
        return email.lower() if email else email

    def create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        
        if not extra_fields.get("is_staff"):
            raise ValueError("Superuser must have is_staff=True.")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Superuser must have is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    email = models.EmailField(unique=True)
    fullname = models.CharField(max_length=CharFieldSizes.MEDIUM)
    profile_picture = models.ImageField(default="default.png", upload_to="profile_images")
    is_darkmode = models.BooleanField(default=False)
    is_cloud_sync = models.BooleanField(default=False)

    username = None

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["fullname"]

    objects = UserManager()
