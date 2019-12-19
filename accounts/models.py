from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver

class User(AbstractUser):
    id = models.AutoField(primary_key=True)
    email = models.EmailField(blank=False, unique=True)
    username = models.CharField(max_length=30, unique=False, null=False)
    has_access = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

@receiver(post_save, sender=User)
def instantiate_superuser(sender, instance, created, **kwargs):
    if created:
        if instance.is_superuser:
            instance.has_access=True
            instance.save()
