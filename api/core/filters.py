import django_filters

from api.groups.models import GroupMember
from api.expenses.models import Expense


class ExpenseFilter(django_filters.FilterSet):
    group = django_filters.NumberFilter(field_name="group_id")

    class Meta:
        model = Expense
        fields = ["group"]


class GroupMemberFilter(django_filters.FilterSet):
    group = django_filters.NumberFilter(field_name="group_id")

    class Meta:
        model = GroupMember
        fields = ["group"]
