import django_filters

from django.db.models import Q
from django.contrib.auth import get_user_model

from api.groups.models import GroupMember
from api.expenses.models import Expense


User = get_user_model()


class UserFilter(django_filters.rest_framework.FilterSet):
    search = django_filters.rest_framework.CharFilter(method='filter_search')
    
    class Meta:
        model = User
        fields = ['search']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(email__icontains=value) | Q(fullname__icontains=value)
        )


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
