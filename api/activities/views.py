from django.contrib.auth import get_user_model

from rest_framework.permissions import IsAuthenticated

from api.core.mixin import GenericDotsViewSet, ListModelMixin

from api.activities.models import Activity
from api.activities.serializers import ActivitySerializer


User = get_user_model()


class ActivityViewset(GenericDotsViewSet, ListModelMixin):
    serializer_class = ActivitySerializer
    queryset = Activity.objects.all()
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return super().get_queryset().filter(receiver=self.request.user).order_by('-id')

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        un_read = queryset.filter(is_read=False)
        un_read.update(is_read=True)
        
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True, context={"request": request})
        return self.get_paginated_response(serializer.data)


from rest_framework.decorators import api_view
from rest_framework.response import Response
from firebase_admin import messaging

@api_view(["POST"])
def send_test_notification(request):
    fcm_token = request.data.get("fcm_token")

    if not fcm_token:
        return Response({"error": "fcm_token is required"}, status=400)

    # Message
    message = messaging.Message(
        token=fcm_token,
        notification=messaging.Notification(
            title="Test Notification",
            body="This is a test message from Firebase Admin"
        ),
        data={  # Optional
            "extra_info": "hello world"
        }
    )

    # Send message
    response = messaging.send(message)

    return Response({"message_id": response})

