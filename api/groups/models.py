from django.db import models
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

from api.core.models import BaseModel, CharFieldSizes


User = get_user_model()


class Group(BaseModel):
    created_by = models.ForeignKey(User, related_name="group_created_by", on_delete=models.CASCADE)
    name = models.CharField(max_length=CharFieldSizes.SMALL)
    description = models.TextField()
    thumbnail = models.ImageField(upload_to="group_thumbnails")

    def __str__(self):
        return f"{self.name} -> {self.created_by}"


class GroupMember(BaseModel):
    group = models.ForeignKey(Group, related_name="members", on_delete=models.CASCADE)
    user = models.ForeignKey(User, related_name="group_memberships", on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ("group", "user")
    
    def __str__(self):
        return f"{self.user} in {self.group.name}"


@receiver(post_save, sender=Group)
def add_creator_as_member(sender, instance, created, **kwargs):
    if created:
        GroupMember.objects.create(group=instance, user=instance.created_by)
