from django.contrib import admin

from api.expenses.models import Expense, ExpenseSplit


admin.site.register(Expense)
admin.site.register(ExpenseSplit)
