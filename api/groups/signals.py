from django.dispatch import receiver
from django.db.models.signals import post_save, pre_delete
from django.contrib.contenttypes.models import ContentType

from api.groups.models import Group, GroupMember
from api.expenses.models import Expense

from api.groups.utils import create_group_member_activities
from api.activities.models import Activity

@receiver(post_save, sender=Group)
def add_creator_as_member(sender, instance, created, **kwargs):
    if created:
        GroupMember.objects.create(group=instance, user=instance.created_by)


@receiver(post_save, sender=GroupMember)
def create_group_member_activity(sender, instance, created, **kwargs):
    if created and instance.user_id != instance.group.created_by_id:
        create_group_member_activities([instance], instance.group.created_by)


@receiver(pre_delete, sender=Group)
def nullify_group_activities(sender, instance, **kwargs):
    group_ct = ContentType.objects.get_for_model(Group)
    Activity.objects.filter(target_content_type=group_ct, target_object_id=instance.id).update(target_content_type=None, target_object_id=None)


@receiver(pre_delete, sender=GroupMember)
def nullify_group_member_activities(sender, instance, **kwargs):
    group_ct = ContentType.objects.get_for_model(Group)
    expense_ct = ContentType.objects.get_for_model(Expense)
    expense_ids = instance.group.group_expenses.values_list("id", flat=True)

    Activity.objects.filter(target_content_type=group_ct, target_object_id=instance.group_id, receiver_id=instance.user_id).update(target_content_type=None, target_object_id=None)
    Activity.objects.filter(target_content_type=expense_ct, target_object_id__in=expense_ids, receiver_id=instance.user_id).update(target_content_type=None, target_object_id=None)
