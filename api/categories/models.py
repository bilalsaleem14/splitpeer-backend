from django.db import models

from api.core.models import BaseModel, CharFieldSizes


class Category(BaseModel):
    name = models.CharField(max_length=CharFieldSizes.MEDIUM)

    def __str__(self):
        return self.name
