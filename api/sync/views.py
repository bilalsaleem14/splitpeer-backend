from django.db import transaction
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .serializers import UnsyncDataSerializer
from .services import OfflineSyncService


class SyncDataView(APIView):
    """Endpoint to sync unsync data from mobile apps"""
    serializer_class = UnsyncDataSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Handle sync data POST request"""
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        session_id = serializer.validated_data['session_id']
        user = request.user

        # Check for existing session
        existing_data = OfflineSyncService.check_existing_session(session_id, user)
        if existing_data:
            print("Existing session found, returning previously synced data.")
            existing_data['session_id'] = session_id
            return Response(OfflineSyncService.serialize_sync_result(existing_data, session_id, request))

        try:
            # Process new sync data
            print("Processing new sync session.")
            with transaction.atomic():
                sync_result = serializer.process_sync_data(user, request)
                OfflineSyncService.create_sync_session(session_id, user, sync_result)

            return Response(OfflineSyncService.serialize_sync_result(sync_result, session_id, request))

        except Exception as e:
            return Response({"error": f"Failed to sync data: {str(e)}"}, status=500)