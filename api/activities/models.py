from django.db import models
from django.contrib.auth import get_user_model

from api.core.models import BaseModel, CharFieldSizes


User = get_user_model()


class Activity(BaseModel):

    class Types(models.TextChoices):
        GROUP_MEMBER_ADD = "group_member_add"
        EXPENSE_CREATE = "expense_create"
        EXPENSE_UPDATE = "expense_update"
    
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="sent_notifications")
    receiver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="received_notifications")
    title = models.CharField(max_length=CharFieldSizes.MEDIUM)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    type = models.CharField(max_length=CharFieldSizes.SMALL, choices=Types.choices)

    def __str__(self):
        return self.title
