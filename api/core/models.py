from django.db import models


class CreatedByModel(models.Model):
    created_by = models.ForeignKey("users.User", on_delete=models.SET_NULL, null=True)

    class Meta:
        abstract = True


class CreatedAtModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class UpdatedAtModel(models.Model):
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(CreatedAtModel, UpdatedAtModel):
    class Meta:
        abstract = True


class CharFieldSizes:
    EXTRA_SMALL = 10
    SMALL = 50
    MEDIUM = 100
    LARGE = 150
    X_Large = 200
    XX_LARGE = 250
    XXX_LARGE = 500
    MAX = 5000
