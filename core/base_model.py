from django.db import models


class BaseModelManager(models.Manager):
    """
    base manager for base model
    """

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class BaseModel(models.Model):
    """
    base model
    """
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False, serialize=False)

    objects = BaseModelManager()

    class Meta:
        abstract = True