import json
import logging

from django.contrib.auth import get_user_model

from firebase_admin import messaging

from api.activities.models import Activity


User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationService:

    def send(self, device_id, title, body, details, badge=1):
        try:
            notification = messaging.Notification(title=title, body=body)
            apns_config = messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(badge=badge)))
            message = messaging.Message(notification=notification, data={"key": json.dumps(details)}, token=device_id, apns=apns_config)
            messaging.send(message)
        except:
            pass

    def create(self, sender, receiver, title, content, type):
        Activity.objects.create(sender=sender, receiver=receiver, title=title, content=content, type=type)

    def send_create(self, title, content, sender, receiver, type, data=None):
        try:
            if data is None:
                data = {}
            self.create(sender=sender, receiver=receiver, title=title, content=content, type=type)
            badge_count = Activity.objects.filter(receiver=receiver, is_read=False).count()

            fcm_user = getattr(receiver, "fcmdevice", None)
            if fcm_user:
                self.send(device_id=fcm_user.registration_id, title=title, body=content, details=data, badge=badge_count)
        except Exception as e:
            logger.error(f"Error while sending push notification: {e}", exc_info=True)
            pass

    def bulk_create(self, activities, create_activity=True):
        try:
            if create_activity:
                created_activities = Activity.objects.bulk_create(activities)
                notification_list = created_activities
            else:
                notification_list = activities
            
            for item in notification_list:
                if isinstance(item, Activity):
                    receiver = item.receiver
                    title = item.title
                    content = item.content
                    data = {}
                else:
                    receiver = item['receiver']
                    title = item['title']
                    content = item['content']
                    data = item.get('data', {})
                
                badge_count = Activity.objects.filter(receiver=receiver, is_read=False).count()
                
                fcm_user = getattr(receiver, "fcmdevice", None)
                if fcm_user:
                    self.send(device_id=fcm_user.registration_id, title=title, body=content, details=data, badge=badge_count)
        except Exception as e:
            logger.error(f"Error while sending bulk push notifications: {e}", exc_info=True)
            pass


notification_service = NotificationService()