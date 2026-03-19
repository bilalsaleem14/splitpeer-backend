import os

from celery import Celery
from celery.schedules import crontab
from django.conf import settings


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()


app.conf.beat_schedule = {
    "fetch_daily_currency_rates": {
        "task": "api.currency.tasks.get_daily_currency_updated_rates",
        "schedule": crontab(hour=settings.GET_CURRENCY_HOUR, minute=settings.GET_CURRENCY_MINUTE),
    },
}
