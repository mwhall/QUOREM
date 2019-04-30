from django.db import models
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    email = models.EmailField(primary_key=True, blank=False)
    username = models.CharField(max_length=30, unique=False, null=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']