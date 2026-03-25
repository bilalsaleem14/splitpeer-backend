from django.contrib import admin

from api.currency.models import CurrencyDropDown, CurrencyRate


@admin.register(CurrencyDropDown)
class CurrencyDropDownAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "symbol", "fullname", "created_at", "updated_at")
    search_fields = ("code", "symbol", "fullname")
    ordering = ("code",)
    list_per_page = 100


@admin.register(CurrencyRate)
class CurrencyRateAdmin(admin.ModelAdmin):
    list_display = (
        "base_currency",
        "currency",
        "rate",
        "date",
    )

    list_filter = (
        "base_currency",
        "currency",
        "date",
    )

    search_fields = (
        "currency",
        "base_currency",
    )

    ordering = ("-date", "currency")
    date_hierarchy = "date"
    list_per_page = 50
    readonly_fields = ()
    fieldsets = (
        ("Currency Information", {"fields": ("base_currency", "currency", "rate")}),
        ("Meta", {"fields": ("date",)}),
    )
