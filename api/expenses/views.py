from rest_framework.permissions import IsAuthenticated

from api.core.mixin import DotsModelViewSet

from api.core.permissions import IsOwner

from api.groups.models import GroupMember
from api.expenses.models import Expense

from api.expenses.serializers import ExpenseSerializer, ExpenseCreateSerializer, ExpenseUpdateSerializer


class ExpenseViewSet(DotsModelViewSet):
    serializer_class = ExpenseSerializer
    serializer_create_class = ExpenseCreateSerializer
    queryset = Expense.objects.all().select_related("group", "paid_by__user", "category", "created_by").prefetch_related("expense_splits__participant__user").order_by("-created_at")
    permission_classes = [IsAuthenticated, IsOwner]
    action_serializers = {
        "partial_update": ExpenseUpdateSerializer,
    }
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        user_groups = GroupMember.objects.filter(user=self.request.user).values_list("group_id", flat=True)
        queryset = queryset.filter(group__id__in=user_groups)
        
        group_id = self.request.query_params.get("group", None)
        if group_id:
            queryset = queryset.filter(group__id=group_id)
        
        return queryset
    
    def get_serializer_create_class(self):
        if self.action in self.action_serializers:
            return self.action_serializers[self.action]
        return super().get_serializer_create_class()
    
    def get_serializer_class(self):
        return self.serializer_class
