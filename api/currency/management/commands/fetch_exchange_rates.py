import requests

from django.core.management.base import BaseCommand

from api.core.services.currency_service import CurrencyService


class Command(BaseCommand):
    help = "Fetch today's exchange rates from open.er-api.com and store them in the database"

    def handle(self, *args, **kwargs):
        self.stdout.write("Fetching exchange rates...")

        try:
            created, updated = CurrencyService.fetch_and_store_rates()
        except requests.RequestException as e:
            self.stderr.write(self.style.ERROR(f"Network error: {e}"))
            return
        except ValueError as e:
            self.stderr.write(self.style.ERROR(str(e)))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {created} rate(s) created, {updated} rate(s) updated."
            )
        )
