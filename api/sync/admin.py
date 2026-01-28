from django.contrib import admin

# Register your models here.

from .models import OfflineSyncSession

admin.site.register(OfflineSyncSession)
