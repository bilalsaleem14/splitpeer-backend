from django.db import transaction
from django.contrib.auth import get_user_model

from rest_framework import status, serializers
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.core.utils import DotsValidationError, get_or_create_user_by_email
from api.expenses.utils import create_expense_activity

from api.groups.models import Group, GroupMember
from api.expenses.models import Expense, ExpenseSplit, ExpenseItem
from api.categories.models import Category

from api.users.serializers import DashboardStatisticsSerializer, DashboardSpendingPatternSerializer


User = get_user_model()


class DashboardStatisticsView(APIView):
    serializer_class = DashboardStatisticsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = self.serializer_class(data=request.query_params, context={'user': request.user})
        serializer.is_valid(raise_exception=True)
        statistics = serializer.to_representation(None)
        return Response(statistics, status=status.HTTP_200_OK)


class DashboardSpendingPatternView(APIView):
    serializer_class = DashboardSpendingPatternSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = self.serializer_class(data=request.query_params, context={'user': request.user})
        serializer.is_valid(raise_exception=True)
        spending_pattern = serializer.to_representation(None)
        return Response(spending_pattern, status=status.HTTP_200_OK)


# class UnsyncGroupSerializer(serializers.Serializer):
#     """Serializer for unsync group data"""
#     name = serializers.CharField(max_length=100)
#     description = serializers.CharField(required=False, allow_blank=True)
#     thumbnail = serializers.ImageField(required=False)
#     members = serializers.ListField(child=serializers.EmailField())


# class UnsyncExpenseSerializer(serializers.Serializer):
#     """Serializer for unsync expense data"""
#     group_name = serializers.CharField()
#     title = serializers.CharField(max_length=100)
#     amount = serializers.DecimalField(max_digits=9, decimal_places=2)
#     paid_by_email = serializers.EmailField()
#     category = serializers.CharField(required=False, allow_blank=True)
#     notes = serializers.CharField(required=False, allow_blank=True)
#     split_type = serializers.ChoiceField(choices=['equal', 'percentage', 'itemized'])
#     participants = serializers.ListField(child=serializers.DictField())


# class UnsyncDataSerializer(serializers.Serializer):
#     """Main serializer for unsync data batch"""
#     is_unsync = serializers.BooleanField(default=False)
#     groups = UnsyncGroupSerializer(many=True, required=False)
#     expenses = UnsyncExpenseSerializer(many=True, required=False)

#     def create_unsync_data(self, authenticated_user):
#         """Process batch unsync data with validation"""
#         groups_data = self.validated_data.get('groups', [])
#         expenses_data = self.validated_data.get('expenses', [])

#         # Validate data integrity before processing
#         self.validate_unsync_data(groups_data, expenses_data)

#         # Track created groups for expense references
#         group_map = {}

#         # Process groups first
#         for group_data in groups_data:
#             group = self.create_unsync_group(group_data, authenticated_user)
#             group_map[group_data['name']] = group

#         # Process expenses
#         for expense_data in expenses_data:
#             self.create_unsync_expense(expense_data, authenticated_user, group_map)

#     def validate_unsync_data(self, groups_data, expenses_data):
#         """Validate unsync data before processing"""
#         # Check for duplicate group names
#         group_names = [g['name'] for g in groups_data]
#         if len(group_names) != len(set(group_names)):
#             raise DotsValidationError({"error": "Duplicate group names in unsync data"})

#         # Validate expense references
#         expense_group_names = set(e['group_name'] for e in expenses_data)
#         available_group_names = set(g['name'] for g in groups_data)

#         missing_groups = expense_group_names - available_group_names
#         if missing_groups:
#             raise DotsValidationError({
#                 "error": f"Expenses reference non-existent groups: {', '.join(missing_groups)}"
#             })

#     def create_unsync_group(self, group_data, user):
#         """Create group from unsync data"""
#         # Create the group with thumbnail if provided
#         group_data_copy = group_data.copy()
#         thumbnail = group_data_copy.pop('thumbnail', None)
#         members = group_data_copy.pop('members', [])

#         group = Group.objects.create(
#             created_by=user,
#             **group_data_copy
#         )

#         # Set thumbnail if provided
#         if thumbnail:
#             group.thumbnail = thumbnail
#             group.save()

#         # Bulk create group members
#         if members:
#             member_users = []
#             for email in members:
#                 member_users.append(get_or_create_user_by_email(email))

#             # Create group members in bulk
#             group_members = [
#                 GroupMember(group=group, user=member_user)
#                 for member_user in member_users
#             ]
#             GroupMember.objects.bulk_create(group_members)

#         return group

#     def create_unsync_expense(self, expense_data, user, group_map):
#         """Create expense from unsync data"""
#         group = group_map.get(expense_data['group_name'])
#         if not group:
#             raise DotsValidationError({"error": f"Group '{expense_data['group_name']}' not found"})

#         # Get or create paid_by user and ensure group membership
#         paid_by_user = get_or_create_user_by_email(expense_data['paid_by_email'])

#         # Get or create group member for paid_by user
#         paid_by_member, created = GroupMember.objects.get_or_create(
#             group=group,
#             user=paid_by_user,
#             defaults={'group': group, 'user': paid_by_user}
#         )

#         # Get category if provided
#         category = None
#         if expense_data.get('category'):
#             category = Category.objects.filter(name__iexact=expense_data['category']).first()

#         # Create expense
#         expense = Expense.objects.create(
#             group=group,
#             title=expense_data['title'],
#             amount=expense_data['amount'],
#             paid_by=paid_by_member,
#             category=category,
#             notes=expense_data.get('notes', ''),
#             split_type=expense_data['split_type'],
#             created_by=user
#         )

#         # Handle split creation based on type
#         self.create_expense_splits(expense, expense_data['participants'])

#         return expense

#     def create_expense_splits(self, expense, participants_data):
#         """Create expense splits based on participants data"""
#         split_methods = {
#             'equal': self.create_equal_splits,
#             'percentage': self.create_percentage_splits,
#             'itemized': self.create_itemized_splits
#         }

#         method = split_methods.get(expense.split_type)
#         if method:
#             method(expense, participants_data)

#     def create_equal_splits(self, expense, participants_data):
#         """Create equal splits with bulk operations"""
#         included_count = len([p for p in participants_data if p.get('is_included', True)])
#         split_amount = expense.amount / included_count if included_count > 0 else 0

#         expense_splits = []

#         for participant_data in participants_data:
#             user = get_or_create_user_by_email(participant_data['email'])

#             # Get or create group member
#             member, _ = GroupMember.objects.get_or_create(
#                 group=expense.group,
#                 user=user
#             )

#             is_included = participant_data.get('is_included', True)
#             amount = split_amount if is_included else None

#             expense_splits.append(ExpenseSplit(
#                 expense=expense,
#                 participant=member,
#                 amount=amount,
#                 is_included=is_included
#             ))

#         # Bulk create all splits
#         ExpenseSplit.objects.bulk_create(expense_splits)

#     def create_percentage_splits(self, expense, participants_data):
#         """Create percentage-based splits with bulk operations"""
#         expense_splits = []

#         for participant_data in participants_data:
#             user = get_or_create_user_by_email(participant_data['email'])

#             # Get or create group member
#             member, _ = GroupMember.objects.get_or_create(
#                 group=expense.group,
#                 user=user
#             )

#             percentage = participant_data.get('percentage')
#             is_included = participant_data.get('is_included', True)

#             amount = None
#             if is_included and percentage:
#                 amount = (expense.amount * percentage) / 100

#             expense_splits.append(ExpenseSplit(
#                 expense=expense,
#                 participant=member,
#                 amount=amount,
#                 percentage=percentage if is_included else None,
#                 is_included=is_included
#             ))

#         # Bulk create all splits
#         ExpenseSplit.objects.bulk_create(expense_splits)

#     def create_itemized_splits(self, expense, participants_data):
#         """Create itemized splits with bulk operations"""
#         expense_items = []
#         expense_splits = []
#         member_cache = {}  # Cache group members

#         # Process all items and collect member assignments
#         for item_data in participants_data:
#             user = get_or_create_user_by_email(item_data['assignee_email'])

#             # Get or create group member (cached)
#             if user.id not in member_cache:
#                 member, _ = GroupMember.objects.get_or_create(
#                     group=expense.group,
#                     user=user
#                 )
#                 member_cache[user.id] = member
#             else:
#                 member = member_cache[user.id]

#             # Create expense item
#             expense_items.append(ExpenseItem(
#                 expense=expense,
#                 title=item_data['title'],
#                 amount=item_data['amount'],
#                 assignee=member
#             ))

#         # Bulk create all items
#         created_items = ExpenseItem.objects.bulk_create(expense_items)

#         # Aggregate amounts per member
#         amount_map = {}
#         for item in created_items:
#             assignee_id = item.assignee_id
#             amount_map[assignee_id] = amount_map.get(assignee_id, 0) + item.amount

#         # Create splits based on aggregated amounts
#         for member_id, total_amount in amount_map.items():
#             expense_splits.append(ExpenseSplit(
#                 expense=expense,
#                 participant_id=member_id,
#                 amount=total_amount,
#                 is_included=True
#             ))

#         # Bulk create all splits
#         ExpenseSplit.objects.bulk_create(expense_splits)


# class SyncDataView(APIView):
#     """Endpoint to sync unsync data from mobile apps"""
#     serializer_class = UnsyncDataSerializer
#     permission_classes = [IsAuthenticated]

#     def post(self, request):
#         serializer = self.get_serializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         try:
#             with transaction.atomic():
#                 # Process batch data
#                 serializer.create_unsync_data(request.user)

#                 # Create activities for all expenses
#                 self.create_activities_for_unsync_data(serializer.validated_data)

#             return Response({"message": "Data synced successfully"})

#         except Exception as e:
#             return Response({"error": f"Failed to sync data: {str(e)}"}, status=500)

#     def create_activities_for_unsync_data(self, validated_data):
#         """Create activities for synced expenses using bulk operations"""
#         expenses_data = validated_data.get('expenses', [])
#         if not expenses_data:
#             return

#         # Get all created expenses in one query
#         group_names = [e['group_name'] for e in expenses_data]
#         groups = Group.objects.filter(
#             name__in=group_names,
#             created_by=self.request.user
#         ).select_related()

#         group_map = {g.name: g for g in groups}

#         # Collect all expense identifiers for bulk query
#         expense_queries = []
#         for expense_data in expenses_data:
#             group = group_map.get(expense_data['group_name'])
#             if group:
#                 expense_queries.append(
#                     Q(group=group) &
#                     Q(title=expense_data['title']) &
#                     Q(amount=expense_data['amount'])
#                 )

#         if expense_queries:
#             # Bulk fetch all expenses
#             combined_query = expense_queries[0]
#             for query in expense_queries[1:]:
#                 combined_query |= query

#             expenses = Expense.objects.filter(combined_query).prefetch_related(
#                 'expense_splits__participant__user'
#             )

#             # Create activities for each expense
#             for expense in expenses:
#                 splits = expense.expense_splits.filter(is_included=True)
#                 member_amount_map = {s.participant_id: s.amount for s in splits}
#                 create_expense_activity(expense, member_amount_map, self.request.user)
