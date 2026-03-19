import logging

from celery import shared_task

from api.core.services.currency_service import CurrencyService


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3, "countdown": 60},
    name="api.currency.tasks.get_daily_currency_updated_rates",
)
def get_daily_currency_updated_rates(self):
    """Fetch fresh exchange rates from open.er-api.com and persist them."""
    logger.info("Running daily currency rate update task.")

    try:
        created, updated = CurrencyService.fetch_and_store_rates()
        logger.info("Currency rates updated: %d created, %d updated.", created, updated)
    except Exception as exc:
        logger.error("Currency rate fetch failed: %s. Retrying...", exc)
        raise
