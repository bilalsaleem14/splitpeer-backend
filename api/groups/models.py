from datetime import timedelta

from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

from api.core.models import BaseModel, CharFieldSizes
from api.currency.models import CurrencyDropDown


User = get_user_model()


class Group(BaseModel):
    client_id = models.CharField(max_length=100, unique=True, null=True, blank=True) 
    created_by = models.ForeignKey(User, related_name="group_created_by", on_delete=models.CASCADE)
    name = models.CharField(max_length=CharFieldSizes.SMALL)
    description = models.TextField()
    thumbnail = models.ImageField(upload_to="group_thumbnails", default="default_group_thumbnail.jpg")
    currency = models.ForeignKey(CurrencyDropDown, on_delete=models.PROTECT, related_name="groups")

    def __str__(self):
        return f"{self.name} -> {self.created_by}"


class GroupMember(BaseModel):
    class Status(models.TextChoices):
        NOT_REQUESTED = "not_requested", "Not Requested"
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    group = models.ForeignKey(Group, related_name="members", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="group_memberships", on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NOT_REQUESTED)
    last_requested_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ("group", "user")
    
    def __str__(self):
        return f"{self.user} in {self.group.name}"

    def can_request_join(self):
        if self.user_id == self.group.created_by_id:
            return False
        if self.status == self.Status.APPROVED:
            return False
        if self.status == self.Status.NOT_REQUESTED:
            return True

        cooldown_minutes = getattr(settings, "GROUP_JOIN_REQUEST_COOLDOWN_MINUTES", 0)
        if self.status == self.Status.REJECTED:
            if cooldown_minutes <= 0 or not self.responded_at:
                return True
            return timezone.now() >= self.responded_at + timedelta(minutes=cooldown_minutes)

        if self.status == self.Status.PENDING:
            if cooldown_minutes > 0 and self.last_requested_at:
                return timezone.now() >= self.last_requested_at + timedelta(minutes=cooldown_minutes)
            return False

        return False
