from datetime import datetime, time

from django.utils import timezone


def get_month_boundaries(self, date=None):
    now = timezone.now()
    
    if date:
        target_month = date.month
        target_year = date.year
    else:
        target_month = now.month
        target_year = now.year
    
    month_start = timezone.make_aware(datetime(target_year, target_month, 1, 0, 0, 0, 0))
    today_end = timezone.make_aware(datetime.combine(now.date(), time(23, 59, 59, 999999)))
    
    return month_start, today_end