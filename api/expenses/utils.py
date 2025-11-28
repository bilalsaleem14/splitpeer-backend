from api.activities.models import Activity

from api.activities.services import notification_service


def create_expense_activity(expense, member_amount_map, triggered_by, is_update=False):
    activity_list = []

    for gm_id, amount in member_amount_map.items():
        gm = expense.group.members.get(id=gm_id)

        if is_update:
            title = "Expense Updated"
            content = f"Expense updated by {triggered_by.fullname if triggered_by != gm.user else 'you'} in the group '{expense.group.name}', '{expense.title}'. Your share has changed to ${amount}."
            activity_type = Activity.Types.EXPENSE_UPDATE
        else:
            title = "New Expense Added"
            content = f"New expense added by {triggered_by.fullname if triggered_by != gm.user else 'you'} in the group '{expense.group.name}', '{expense.title}'. Your share is ${amount}."
            activity_type = Activity.Types.EXPENSE_CREATE

        activity_list.append(Activity(sender=triggered_by, receiver=gm.user, type=activity_type, title=title, content=content))

    # Activity.objects.bulk_create(activity_list)
    notification_service.bulk_create(activity_list, create_activity=True)
