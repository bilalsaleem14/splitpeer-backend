from django.dispatch import receiver
from django.db.models.signals import pre_delete
from django.contrib.contenttypes.models import ContentType

from api.expenses.models import Expense
from api.activities.models import Activity


@receiver(pre_delete, sender=Expense)
def nullify_expense_activities(sender, instance, **kwargs):
    expense_ct = ContentType.objects.get_for_model(Expense)
    Activity.objects.filter(target_content_type=expense_ct, target_object_id=instance.id).update(target_content_type=None, target_object_id=None)
