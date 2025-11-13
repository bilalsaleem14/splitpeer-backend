from datetime import timedelta, datetime

from django.utils import timezone

from rest_framework.generics import get_object_or_404


def get_user(self):
    queryset = self.filter_queryset(self.get_queryset())

    lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

    assert lookup_url_kwarg in self.kwargs, (
        "Expected view %s to be called with a URL keyword argument "
        'named "%s". Fix your URL conf, or set the `.lookup_field` '
        "attribute on the view correctly." % (self.__class__.__name__, lookup_url_kwarg)
    )

    filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
    obj = get_object_or_404(queryset, **filter_kwargs)

    self.check_object_permissions(self.request, obj)

    return obj


def get_start_end_time(frequency, date_param=None):
    # Get date range based on frequency

    now = timezone.now()
    if date_param:
        try:
            target_date = datetime.strptime(date_param, "%d-%m-%Y")
            target_date = timezone.make_aware(target_date) if timezone.is_naive(target_date) else target_date
        except ValueError:
            target_date = now
    else:
        target_date = now

    if frequency == "day":
        start_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif frequency == "week":
        # Get Monday of current week
        days_since_monday = target_date.weekday()
        monday = target_date - timedelta(days=days_since_monday)
        start_date = monday.replace(hour=0, minute=0, second=0, microsecond=0)
        # Get Sunday of current week
        sunday = monday + timedelta(days=6)
        end_date = sunday.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif frequency == "month":
        # First day of current month
        start_date = target_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        # Last day of current month
        if target_date.month == 12:
            next_month = target_date.replace(year=target_date.year + 1, month=1, day=1)
        else:
            next_month = target_date.replace(month=target_date.month + 1, day=1)
        last_day = next_month - timedelta(days=1)
        end_date = last_day.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif frequency == "last_month":
        first_of_this_month = target_date.replace(day=1)
        last_month_last_day = first_of_this_month - timedelta(days=1)
        start_date = last_month_last_day.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end_date = last_month_last_day.replace(hour=23, minute=59, second=59, microsecond=999999)
    else:
        start_date = None
        end_date = None

    return start_date, end_date
