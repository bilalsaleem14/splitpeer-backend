from urllib.parse import urlencode

from django.core import signing
from django.db.models import Count, DecimalField, Exists, IntegerField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.conf import settings

from api.activities.models import Activity
from api.expenses.models import Expense
from api.groups.models import Group, GroupMember

from api.activities.services import notification_service


# Return the GroupMember record for a user in a group, leveraging prefetched members when available.
def get_user_group_membership(group, user):
    if not group or not user or not getattr(user, "is_authenticated", False):
        return None
    for member in group.members.all():
        if member.user_id == user.id:
            return member
    return None


# Return True if the user is the group creator or an approved member of the group.
def is_approved_group_member(group, user):
    if not group or not user or not getattr(user, "is_authenticated", False):
        return False
    if group.created_by_id == user.id:
        return True
    member = get_user_group_membership(group, user)
    return bool(member and member.status == GroupMember.Status.APPROVED)


# Filter a queryset with a group relation to only groups where the user is an approved member.
def filter_by_approved_group_member(queryset, user, group_lookup="group"):
    return queryset.filter(**{f"{group_lookup}__members__user": user, f"{group_lookup}__members__status": GroupMember.Status.APPROVED}).distinct()


def generate_group_join_token(member, action):
    payload = {
        "member_id": member.id,
        "group_id": member.group_id,
        "action": action,
    }
    return signing.dumps(payload, salt=settings.SECRET_KEY)


def verify_group_join_token(token, max_age=None):
    return signing.loads(token, salt=settings.SECRET_KEY, max_age=max_age)


def build_group_join_action_urls(request, member):
    respond_path = reverse("groups-respond-join-request")
    approve_token = generate_group_join_token(member, "approve")
    reject_token = generate_group_join_token(member, "reject")

    approve_url = request.build_absolute_uri(f"{respond_path}?{urlencode({'token': approve_token})}")
    reject_url = request.build_absolute_uri(f"{respond_path}?{urlencode({'token': reject_token})}")
    return approve_url, reject_url


def create_group_member_activities(members, sender_user):
    activity_objects = []

    for member in members:
        group = member.group
        receiver_user = member.user

        activity_objects.append(Activity(
            sender=sender_user,
            receiver=receiver_user,
            type=Activity.Types.GROUP_MEMBER_ADD,
            title="Added in a New Group",
            content=f"You have been added to the new group '{group.name}' "
                    f"created by '{sender_user.fullname}': "
                    f"check your split now!",
            target=member.group
        ))

    notification_service.bulk_create(activity_objects, create_activity=True)


def annotate_group_queryset(queryset):
    expenses_sum_subquery = Expense.objects.filter(group=OuterRef("pk")).values("group").annotate(total=Sum("amount")).values("total")
    members_count_subquery = GroupMember.objects.filter(group=OuterRef("pk")).exclude(user=OuterRef("created_by")).values("group").annotate(count=Count("pk")).values("count")
    return (
        queryset.select_related("created_by")
        .prefetch_related("members__user")
        .annotate(
            members_count_annotated=Coalesce(Subquery(members_count_subquery, output_field=IntegerField()), 0),
            total_expenses_annotated=Coalesce(Subquery(expenses_sum_subquery, output_field=DecimalField()), Value(0, output_field=DecimalField())),
        )
    )


def get_common_groups_queryset(user, friend_user):
    user_member_exists = GroupMember.objects.filter(group=OuterRef("pk"), user=user)
    friend_member_exists = GroupMember.objects.filter(group=OuterRef("pk"), user=friend_user)
    queryset = Group.objects.annotate(is_user=Exists(user_member_exists), is_friend=Exists(friend_member_exists)).filter(is_user=True, is_friend=True)
    return annotate_group_queryset(queryset).order_by("-id")
