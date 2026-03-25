import requests

from datetime import date
from decimal import Decimal

from api.currency.models import CurrencyRate


EXCHANGE_RATE_API_URL = "https://open.er-api.com/v6/latest/USD"


class CurrencyService:

    @staticmethod
    def get_rate(currency):

        if currency == "USD":
            return Decimal("1")

        rate = CurrencyRate.objects.filter(
            currency=currency,
            date=date.today()
        ).first()

        if not rate:
            raise Exception("Currency rate not available")

        return rate.rate

    @staticmethod
    def convert_to_usd(amount, currency):

        if currency == "USD":
            return amount, Decimal("1")

        rate = CurrencyService.get_rate(currency)
        usd_amount = amount / rate

        return usd_amount, rate

    @staticmethod
    def fetch_and_store_rates():
        """
        Fetch today's exchange rates from open.er-api.com and upsert them
        into CurrencyRate. Returns a (created, updated) count tuple.
        Raises requests.RequestException on network failure.
        """
        response = requests.get(EXCHANGE_RATE_API_URL, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data.get("result") != "success":
            raise ValueError(f"Exchange rate API returned: {data.get('result')}")

        rates = data.get("rates", {})
        today = date.today()
        created = updated = 0

        # Store all currencies returned by the API so the group dropdown can support
        # any selected currency code (not just a small hardcoded set).
        for currency, rate_value in rates.items():
            if rate_value is None:
                continue

            _, was_created = CurrencyRate.objects.update_or_create(
                currency=str(currency),
                date=today,
                defaults={
                    "base_currency": "USD",
                    "rate": Decimal(str(rate_value)),
                },
            )

            if was_created:
                created += 1
            else:
                updated += 1

        return created, updated