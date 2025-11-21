from django.db import models
from django.contrib.auth import get_user_model

from api.core.models import BaseModel


User = get_user_model()


class Friend(BaseModel):
    created_by = models.ForeignKey(User, related_name="friend_created_by", on_delete=models.CASCADE)
    member = models.ForeignKey(User, related_name="friend_of", on_delete=models.CASCADE)

    class Meta:
        unique_together = ("created_by", "member")

    def __str__(self):
        return f"{self.created_by} -> {self.member}"
