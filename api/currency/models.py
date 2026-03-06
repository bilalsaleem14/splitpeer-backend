from django.db import models


class CurrencyRate(models.Model):
    base_currency = models.CharField(max_length=3, default="USD")
    currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    date = models.DateField()

    class Meta:
        unique_together = ("currency", "date")

    def __str__(self):
        return f"{self.base_currency} -> {self.currency} ({self.rate}) {self.date}"