from django.db import transaction
from django.contrib.auth import get_user_model

from api.core.otp_helper import send_invite_email
from api.core.utils import DotsValidationError, get_or_create_user_by_email
from api.expenses.utils import create_expense_activity

from api.groups.models import Group, GroupMember
from api.expenses.models import Expense, ExpenseSplit, ExpenseItem
from api.categories.models import Category
from api.friends.models import Friend
from .models import OfflineSyncSession

from api.friends.serializers import FriendSerializer
from api.groups.serializers import GroupSerializer, GroupMemberSerializer
from api.expenses.serializers import ExpenseSerializer
from decimal import Decimal

User = get_user_model()


class OfflineSyncService:
    """Service class for handling offline data synchronization"""

    @staticmethod
    def process_unsync_data(validated_data, authenticated_user, request):
        """Process batch unsync data with validation in dependency order"""
        print("Validating unsync data integrity.")
        OfflineSyncService.validate_unsync_data(validated_data)

        result = OfflineSyncService._process_data_in_order(validated_data, authenticated_user)

        is_synced = OfflineSyncService.create_activities_for_unsync_data(result['created_expenses'], request)

        result['is_synced'] = is_synced
        return result

    @staticmethod
    def check_existing_session(session_id, user):
        """Check if a sync session already exists and return its data"""

        existing_session = OfflineSyncSession.objects.filter(
            session_id=session_id,
            user=user
        ).first()

        if not existing_session:
            return None

        # Fetch existing session data
        friends = []
        if existing_session.friend_emails:
            friend_users = User.objects.filter(email__in=existing_session.friend_emails)
            friends = Friend.objects.filter(
                created_by=user,
                member__in=friend_users
            ).select_related('member')

        groups = Group.objects.filter(client_id__in=existing_session.group_client_ids, created_by=user)
        expenses = Expense.objects.filter(client_id__in=existing_session.expense_client_ids, created_by=user)

        group_members = GroupMember.objects.filter(
            group__in=groups,
            user__email__in=existing_session.friend_emails
        ).select_related('user', 'group')

        return {
            'friends': friends,
            'groups': groups,
            'group_members': group_members,
            'expenses': expenses
        }

    @staticmethod
    def serialize_sync_result(sync_result, session_id, request):
        """Serialize sync results for API response"""

        if not isinstance(sync_result, dict):
            raise ValueError(f"sync_result must be a dict, got {type(sync_result)}")

        friends_data = sync_result.get('friends') or sync_result.get('created_friends', [])
        groups_data = sync_result.get('groups') or sync_result.get('created_groups', [])
        group_members_data = sync_result.get('group_members') or sync_result.get('created_group_members', [])
        expenses_data = sync_result.get('expenses') or sync_result.get('created_expenses', [])

        friend_serializer = FriendSerializer(friends_data, many=True, context={'request': request})
        group_serializer = GroupSerializer(groups_data, many=True, context={'request': request})
        group_member_serializer = GroupMemberSerializer(group_members_data, many=True, context={'request': request})
        expense_serializer = ExpenseSerializer(expenses_data, many=True, context={'request': request})

        return {
            "data": {
                "session_id": session_id,
                "friends": friend_serializer.data,
                "groups": group_serializer.data,
                "group_members": group_member_serializer.data,
                "expenses": expense_serializer.data
            }
        }

    @staticmethod
    def create_sync_session(session_id, user, sync_result):
        """Create a record of the sync session"""

        print("Creating offline sync session record.")

        created_friends = sync_result.get('created_friends', [])
        created_groups = sync_result.get('created_groups', [])
        created_group_members = sync_result.get('created_group_members', [])
        created_expenses = sync_result.get('created_expenses', [])

        friend_emails = [friend.member.email for friend in created_friends if hasattr(friend, 'member')]
        group_client_ids = [group.client_id for group in created_groups if hasattr(group, 'client_id')]
        expense_client_ids = [expense.client_id for expense in created_expenses if hasattr(expense, 'client_id')]

        OfflineSyncSession.objects.create(
            session_id=session_id,
            user=user,
            friends_created=len(created_friends),
            groups_created=len(created_groups),
            group_members_created=len(created_group_members),
            expenses_created=len(created_expenses),
            friend_emails=friend_emails,
            group_client_ids=group_client_ids,
            expense_client_ids=expense_client_ids,
            is_all_synced=sync_result.get('is_synced', False)
        )

        print("Sync session record created successfully.")

    @staticmethod
    def _process_data_in_order(validated_data, authenticated_user):
        """Process data in dependency order and return results"""
        # Track created objects
        group_map = {}
        created_friends = []
        created_groups = []
        created_group_members = []
        created_expenses = []

        # 1. Process friends first
        for friend_data in validated_data.get('friends', []):
            friend, created = OfflineSyncService.create_unsync_friend(friend_data, authenticated_user)
            if friend is not None and friend not in created_friends:
                created_friends.append(friend)

        # 2. Process groups second
        for group_data in validated_data.get('groups', []):
            group, created = OfflineSyncService.create_unsync_group(group_data, authenticated_user)
            group_map[group_data['client_id']] = group  
            if created:
                created_groups.append(group)
                # post_save signal in api/groups/signals.py (add_creator_as_member) auto-creates creator's GroupMember
                creator_member = GroupMember.objects.filter(group=group, user=authenticated_user).first()
                if creator_member and creator_member not in created_group_members:
                    created_group_members.append(creator_member)

        # 3. Process explicit group memberships third
        for membership_data in validated_data.get('group_members', []):
            group_member, created = OfflineSyncService.create_unsync_group_membership(membership_data, authenticated_user, group_map)
            if group_member is not None and group_member not in created_group_members:
                created_group_members.append(group_member)  

        # 4. Process expenses last 
        for expense_data in validated_data.get('expenses', []):
            expense, created = OfflineSyncService.create_unsync_expense(expense_data, authenticated_user, group_map)
            if created:
                created_expenses.append(expense)

        # Ensure all keys exist even if empty
        result = {
            'created_friends': created_friends,
            'created_groups': created_groups,
            'created_group_members': created_group_members,
            'created_expenses': created_expenses,
            'is_synced': True
        }

        print(f"Sync result summary: {len(created_friends)} friends, {len(created_groups)} groups, {len(created_group_members)} members, {len(created_expenses)} expenses")
        return result

    @staticmethod
    def validate_unsync_data(validated_data):
        """Validate unsync data before processing"""
        groups_data = validated_data.get('groups', [])
        expenses_data = validated_data.get('expenses', [])

        print("Checking for duplicate group client_ids in unsync data.")
        group_client_ids = [g['client_id'] for g in groups_data]
        print(f"Group client_ids found: {group_client_ids}")
        print(f"Set of group client_ids: {set(group_client_ids)}")
        print(f"Lengths - list: {len(group_client_ids)}, set: {len(set(group_client_ids))}")
        if len(group_client_ids) != len(set(group_client_ids)):
            raise DotsValidationError({"error": "Duplicate group client_ids in unsync data"})

        expense_group_client_ids = set(e['group_client_id'] for e in expenses_data)
        available_group_client_ids = set(g['client_id'] for g in groups_data)

        missing_groups = expense_group_client_ids - available_group_client_ids
        print(f"Validating expense group references. Missing groups: {missing_groups}")
        print(f"Expense group client_ids: {expense_group_client_ids}")
        print(f"Available group client_ids: {available_group_client_ids}")
        if missing_groups:
            raise DotsValidationError({
                "error": f"Expenses reference non-existent groups: {', '.join(missing_groups)}"
            })

    @staticmethod
    def is_self_email(email, current_user):
        """Check if an email represents the authenticated request user or 'me@gmail.com'."""
        if not email or not current_user:
            return False
        normalized = email.strip().lower()
        user_email = (getattr(current_user, "email", "") or "").strip().lower()
        return normalized == "me@gmail.com" or (bool(user_email) and normalized == user_email)

    @staticmethod
    def resolve_sync_user(email, current_user):
        """Resolve email to the authenticated user if self-email, otherwise get_or_create user."""
        if OfflineSyncService.is_self_email(email, current_user):
            return current_user
        return get_or_create_user_by_email(email)

    @staticmethod
    def create_unsync_friend(friend_data, user):
        """Create friend relationship in sync context (idempotent)"""
        print("Creating unsync friend relationship.")
        email = friend_data['email']
        if OfflineSyncService.is_self_email(email, user):
            return None, False

        friend_user = get_or_create_user_by_email(email)

        # Create friend relationship (idempotent)
        friend, created = Friend.objects.get_or_create(
            created_by=user,
            member=friend_user,
            defaults={'created_by': user, 'member': friend_user}
        )

        # Send invitation email if this is a new friend relationship
        if created:
            print(f"Sending invite email to {email} in create_unsync_friend .")
            send_invite_email(email, user)

        print(f"Friend relationship created: {created}")
        print(f"Friend details: {friend}")
        return friend, created

    @staticmethod
    def create_unsync_group(group_data, user):
        """Create group from unsync data (idempotent)"""
        from api.currency.models import CurrencyDropDown
        print("Creating unsync group.")
        client_id = group_data['client_id']
        currency_code = group_data.get("currency", "")

        try:
            currency = CurrencyDropDown.objects.get(code=currency_code)
        except CurrencyDropDown.DoesNotExist:
            currency = CurrencyDropDown.objects.get(code="USD")

        # Create or get existing group
        group, created = Group.objects.get_or_create(
            client_id=client_id,
            defaults={
                'name': group_data['name'],
                'description': group_data.get('description', ''),
                'created_by': user,
                'currency': currency
            }
        )

        print(f"Group created: {created}")
        print(f"Group details: {group}")
        return group, created

    @staticmethod
    def create_unsync_group_membership(membership_data, user, group_map):
        """Create group membership in sync context (idempotent)"""
        print("Creating unsync group membership.")
        group_client_id = membership_data['group_client_id']
        member_email = membership_data['member_email']

        group = group_map.get(group_client_id)
        if not group:
            raise DotsValidationError({"error": f"Group '{group_client_id}' not found"})

        member_user = OfflineSyncService.resolve_sync_user(member_email, user)
        # Create group membership (idempotent)
        group_member, created = GroupMember.objects.get_or_create(
            group=group,
            user=member_user,
            defaults={'group': group, 'user': member_user}
        )

        print(f"Group membership created: {created}")
        print(f"GroupMember details: {group_member}")
        return group_member, created

    @staticmethod
    def create_unsync_expense(expense_data, user, group_map):
        """Create expense from unsync data (idempotent)"""
        from api.core.services.currency_service import CurrencyService
        print("Creating unsync expense.")
        group_client_id = expense_data['group_client_id']
        group = group_map.get(group_client_id)
        if not group:
            raise DotsValidationError({"error": f"Group '{group_client_id}' not found"})

        paid_by_user = OfflineSyncService.resolve_sync_user(expense_data['paid_by_email'], user)

        paid_by_member, _ = GroupMember.objects.get_or_create(
            group=group,
            user=paid_by_user,
            defaults={'group': group, 'user': paid_by_user}
        )

        category = None
        if expense_data.get('category'):
            category = Category.objects.filter(name__iexact=expense_data['category']).first()

        expense_amount = Decimal(str(expense_data['amount']))
        group_currency_code = group.currency.code
        amount_usd = expense_amount
        exchange_rate = Decimal("1")

        if not group_currency_code == "USD":
            try:
                amount_usd, exchange_rate = CurrencyService.convert_to_usd(expense_amount, group_currency_code)
            except Exception:
                pass

        expense, created = Expense.objects.get_or_create(
            client_id=expense_data['client_id'],
            defaults={
                'group': group,
                'title': expense_data['title'],
                'amount': Decimal(str(expense_data['amount'])),
                'paid_by': paid_by_member,
                'category': category,
                'notes': expense_data.get('notes', ''),
                'split_type': expense_data['split_type'],
                'created_by': user,
                'currency': group_currency_code,
                'amount_usd': amount_usd,
                'exchange_rate': exchange_rate
            }
        )

        if created:
            OfflineSyncService.create_expense_splits(expense, expense_data, user)

        print(f"Expense created: {created}")
        print(f"Expense details: {expense}")
        return expense, created

    @staticmethod
    def create_expense_splits(expense, expense_data, current_user=None):
        """Create expense splits based on expense data (participants and/or items)"""
        user = current_user or expense.created_by
        print("Creating expense splits.")

        if isinstance(expense_data, dict):
            participants_data = expense_data.get('participants', [])
            items_data = expense_data.get('items', [])
        else:
            participants_data = expense_data
            items_data = []

        split_methods = {
            'equal': lambda exp, p_data, u: OfflineSyncService.create_equal_splits(exp, p_data, u),
            'percentage': lambda exp, p_data, u: OfflineSyncService.create_percentage_splits(exp, p_data, u),
            'itemized': lambda exp, p_data, u: OfflineSyncService.create_itemized_splits(exp, p_data, u, items_data=items_data)
        }

        method = split_methods.get(expense.split_type)
        print(f"Using split method: {expense.split_type}")
        print(f"Participants data: {participants_data}")
        print(f"Expense ID: {expense.id}, Amount: {expense.amount}")
        print(f"method found:{method} {method is not None}")
        if method:
            print(f"method exists, proceeding to create splits.{method}")
            method(expense, participants_data, user)

    @staticmethod
    def create_equal_splits(expense, participants_data, current_user=None):
        """Create equal splits with bulk operations"""
        user = current_user or expense.created_by
        print("Creating equal splits.")

        member_map = {}
        for participant_data in participants_data:
            p_user = OfflineSyncService.resolve_sync_user(participant_data['email'], user)
            member, _ = GroupMember.objects.get_or_create(
                group=expense.group,
                user=p_user
            )
            is_included = participant_data.get('is_included', True)
            if member.id not in member_map:
                member_map[member.id] = (member, is_included)
            else:
                prev_member, prev_included = member_map[member.id]
                member_map[member.id] = (member, prev_included or is_included)

        included_members = [m for m, inc in member_map.values() if inc]
        included_count = len(included_members)

        split_amount = Decimal("0.00")
        remainder = Decimal("0.00")
        if included_count > 0:
            base_amount = (expense.amount / Decimal(str(included_count))).quantize(Decimal("0.01"))
            split_amount = base_amount
            remainder = expense.amount - (base_amount * Decimal(str(included_count)))

        expense_splits = []
        first_included = True
        for member_id, (member, is_included) in member_map.items():
            amount = None
            if is_included:
                amount = split_amount
                if first_included and remainder != Decimal("0.00"):
                    amount += remainder
                    first_included = False

            expense_splits.append(ExpenseSplit(
                expense=expense,
                participant=member,
                amount=amount,
                is_included=is_included
            ))

        ExpenseSplit.objects.bulk_create(expense_splits)

    @staticmethod
    def create_percentage_splits(expense, participants_data, current_user=None):
        """Create percentage-based splits with bulk operations"""
        user = current_user or expense.created_by
        print("Creating percentage-based splits.")

        member_map = {}
        for participant_data in participants_data:
            p_user = OfflineSyncService.resolve_sync_user(participant_data['email'], user)
            member, _ = GroupMember.objects.get_or_create(
                group=expense.group,
                user=p_user
            )
            percentage = participant_data.get('percentage')
            is_included = participant_data.get('is_included', True)

            if member.id not in member_map:
                member_map[member.id] = (member, Decimal(str(percentage)) if percentage is not None else None, is_included)
            else:
                prev_member, prev_percentage, prev_included = member_map[member.id]
                total_pct = (prev_percentage or Decimal("0")) + (Decimal(str(percentage)) if percentage is not None else Decimal("0"))
                member_map[member.id] = (member, total_pct, prev_included or is_included)

        expense_splits = []
        for member_id, (member, percentage, is_included) in member_map.items():
            amount = None
            if is_included and percentage is not None:
                amount = ((expense.amount * percentage) / Decimal("100")).quantize(Decimal("0.01"))

            expense_splits.append(ExpenseSplit(
                expense=expense,
                participant=member,
                amount=amount,
                percentage=percentage.quantize(Decimal("0.01")) if (percentage is not None and is_included) else None,
                is_included=is_included
            ))

        ExpenseSplit.objects.bulk_create(expense_splits)

    @staticmethod
    def create_itemized_splits(expense, participants_data, current_user=None, items_data=None):
        """Create itemized splits with bulk operations"""
        user = current_user or expense.created_by
        print("Creating itemized splits.")
        expense_items = []
        expense_splits = []
        member_cache = {}

        raw_items = items_data or []
        if not raw_items:
            # Fallback for backward compatibility if items are passed inside participants
            raw_items = [p for p in participants_data if 'assignee_email' in p]

        for item_data in raw_items:
            assignee_user = OfflineSyncService.resolve_sync_user(item_data['assignee_email'], user)

            if assignee_user.id not in member_cache:
                member, _ = GroupMember.objects.get_or_create(
                    group=expense.group,
                    user=assignee_user
                )
                member_cache[assignee_user.id] = member
            else:
                member = member_cache[assignee_user.id]

            item_amount = Decimal(str(item_data['amount'])).quantize(Decimal("0.01"))
            expense_items.append(ExpenseItem(
                expense=expense,
                title=item_data['title'],
                amount=item_amount,
                assignee=member
            ))

        created_items = ExpenseItem.objects.bulk_create(expense_items)

        amount_map = {}
        for item in created_items:
            assignee_id = item.assignee_id
            amount_map[assignee_id] = amount_map.get(assignee_id, Decimal("0.00")) + Decimal(str(item.amount))

        # Create splits for participants who have items
        for member_id, total_amount in amount_map.items():
            expense_splits.append(ExpenseSplit(
                expense=expense,
                participant_id=member_id,
                amount=total_amount,
                is_included=True
            ))

        # Also handle any participants explicitly passed with 'email' who have 0 items
        for participant_data in participants_data:
            if 'email' in participant_data and 'assignee_email' not in participant_data:
                p_user = OfflineSyncService.resolve_sync_user(participant_data['email'], user)
                if p_user.id not in member_cache:
                    member, _ = GroupMember.objects.get_or_create(
                        group=expense.group,
                        user=p_user
                    )
                    member_cache[p_user.id] = member
                else:
                    member = member_cache[p_user.id]

                if member.id not in amount_map:
                    expense_splits.append(ExpenseSplit(
                        expense=expense,
                        participant=member,
                        amount=None,
                        is_included=False
                    ))

        ExpenseSplit.objects.bulk_create(expense_splits)

    @staticmethod
    def create_activities_for_unsync_data(created_expenses, request):
        print("Creating activities for newly created expenses.")

        if not created_expenses:
            print("No new expenses created. Skipping activity creation.")
            return True

        for expense in created_expenses:
            splits = expense.expense_splits.filter(is_included=True)
            member_amount_map = {
                s.participant_id: s.amount.quantize(Decimal("0.01")) for s in splits if s.amount is not None
            }

            print(
                f"Creating activity for NEW expense ID {expense.id} "
                f"with splits: {member_amount_map}"
            )

            create_expense_activity(
                expense,
                member_amount_map,
                request.user
            )

        return True