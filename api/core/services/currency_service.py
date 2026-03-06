from datetime import date
from decimal import Decimal

from api.currency.models import CurrencyRate


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