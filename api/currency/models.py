from django.db import models
from django.utils import timezone
from api.core.models import CharFieldSizes


class CurrencyRate(models.Model):
    base_currency = models.CharField(max_length=3, default="USD")
    currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=12, decimal_places=6)
    date = models.DateField()

    class Meta:
        unique_together = ("currency", "date")

    def __str__(self):
        return f"{self.base_currency} -> {self.currency} ({self.rate}) {self.date}"



class CurrencyDropDown(models.Model):
    fullname = models.CharField(max_length=CharFieldSizes.LARGE, unique=True)
    code = models.CharField(max_length=10, unique=True ) 
    symbol = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.code} - {self.fullname}"