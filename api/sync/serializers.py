from rest_framework import serializers

from .services import OfflineSyncService


class UnsyncFriendSerializer(serializers.Serializer):
    """Serializer for unsync friend data"""
    email = serializers.EmailField(required=True)


class UnsyncGroupMemberSerializer(serializers.Serializer):
    """Serializer for unsync group membership data"""
    group_client_id = serializers.CharField(max_length=100, required=True)
    member_email = serializers.EmailField(required=True)


class UnsyncGroupSerializer(serializers.Serializer):
    """Serializer for unsync group data"""
    client_id = serializers.CharField(max_length=100, required=True)  
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True)
    thumbnail = serializers.ImageField(required=False)
    members = serializers.ListField(child=serializers.EmailField())


class UnsyncExpenseSerializer(serializers.Serializer):
    """Serializer for unsync expense data"""
    client_id = serializers.CharField(max_length=100, required=True)  
    group_client_id = serializers.CharField(max_length=100, required=True) 
    title = serializers.CharField(max_length=100)
    amount = serializers.DecimalField(max_digits=9, decimal_places=2)
    paid_by_email = serializers.EmailField()
    category = serializers.CharField(required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    split_type = serializers.ChoiceField(choices=['equal', 'percentage', 'itemized'])
    participants = serializers.ListField(child=serializers.DictField())


class UnsyncDataSerializer(serializers.Serializer):
    """Main serializer for unsync data batch with processing logic"""
    session_id = serializers.CharField(max_length=100, required=True) 
    is_unsync = serializers.BooleanField(default=False)
    friends = UnsyncFriendSerializer(many=True, required=False)
    groups = UnsyncGroupSerializer(many=True, required=False)
    group_members = UnsyncGroupMemberSerializer(many=True, required=False)
    expenses = UnsyncExpenseSerializer(many=True, required=False)

    def process_sync_data(self, user, request):
        """Process the validated sync data using the service layer"""
        return OfflineSyncService.process_unsync_data(
            self.validated_data,
            user,
            request
        )