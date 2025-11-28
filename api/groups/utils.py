from api.activities.models import Activity

from api.activities.services import notification_service


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
        ))

    # Activity.objects.bulk_create(activity_objects)
    notification_service.bulk_create(activity_objects, create_activity=True)
