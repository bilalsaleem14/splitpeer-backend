from django.db import models
from django.contrib.auth import get_user_model

from api.core.models import BaseModel, CharFieldSizes
from api.core.otp_helper import get_otp_verified_token


User = get_user_model()


class OTP(BaseModel):
    
    class Type(models.TextChoices):
        CREATE = "create"
        FORGOT = "forgot"
        CHANGE = "change"

    email = models.EmailField(null=True, blank=True)
    code = models.IntegerField()
    type = models.CharField(max_length=CharFieldSizes.SMALL, choices=Type.choices)
    verification_token = models.CharField(max_length=200)
    used = models.BooleanField(default=False)
    timeout = models.DateTimeField()

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not self.verification_token:
            self.verification_token = get_otp_verified_token(otp=self.code, content=self.email)

    def __str__(self):
        return self.email
