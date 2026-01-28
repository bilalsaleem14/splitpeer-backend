from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class OfflineSyncSession(models.Model):
    """Track offline data sync sessions to prevent duplicates"""
    session_id = models.CharField(max_length=100)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    processed_at = models.DateTimeField(auto_now_add=True)
    friends_created = models.IntegerField(default=0)
    groups_created = models.IntegerField(default=0)
    group_members_created = models.IntegerField(default=0)
    expenses_created = models.IntegerField(default=0)
    friend_emails = models.JSONField(default=list)
    group_client_ids = models.JSONField(default=list)
    expense_client_ids = models.JSONField(default=list)
    is_all_synced = models.BooleanField(default=False)

    class Meta:
        ordering = ['-processed_at']

    def __str__(self):
        return f"Sync {self.session_id} by {self.user.email}"

    @property
    def total_items_created(self):
        """Get total number of items created in this session"""
        return (self.friends_created + self.groups_created +
                self.group_members_created + self.expenses_created)

    def get_created_items_summary(self):
        """Get a summary of items created"""
        return {
            'friends': self.friends_created,
            'groups': self.groups_created,
            'group_members': self.group_members_created,
            'expenses': self.expenses_created,
            'total': self.total_items_created
        }

    def is_successful_sync(self):
        """Check if the sync was successful"""
        return self.is_all_synced and self.total_items_created > 0
