from django.db.models.signals import post_save
from django.dispatch import receiver

from api.groups.models import Group, GroupMember

from api.groups.utils import create_group_member_activities


@receiver(post_save, sender=Group)
def add_creator_as_member(sender, instance, created, **kwargs):
    if created:
        GroupMember.objects.create(group=instance, user=instance.created_by)


@receiver(post_save, sender=GroupMember)
def create_group_member_activity(sender, instance, created, **kwargs):
    if created and instance.user_id != instance.group.created_by_id:
        create_group_member_activities([instance], instance.group.created_by)
