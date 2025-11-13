import os

from django.db.models import FileField, ImageField
from django.db.models.signals import post_delete, pre_save, post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from api.groups.models import Group


User = get_user_model()


def delete_instance_media(instance):
    for field in instance._meta.fields:
        if isinstance(field, (FileField, ImageField)):
            file = getattr(instance, field.name)
            if file and file.name != "default.png":
                file_path = file.path
                if os.path.exists(file_path):
                    os.remove(file_path)


@receiver(post_delete, sender=User)
@receiver(post_delete, sender=Group)
def delete_media_on_delete(sender, instance, **kwargs):
    delete_instance_media(instance)


@receiver(pre_save, sender=User)
@receiver(pre_save, sender=Group)
def delete_old_media_on_update(sender, instance, **kwargs):
    if not instance.pk:
        return

    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    for field in instance._meta.fields:
        if isinstance(field, (FileField, ImageField)):
            old_file = getattr(old_instance, field.name)
            new_file = getattr(instance, field.name)

            if old_file and old_file.name and old_file != new_file:
                if old_file.name != "default.png" and os.path.exists(old_file.path):
                    os.remove(old_file.path)
