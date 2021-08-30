from django.apps import AppConfig


class DbConfig(AppConfig):
    name = 'db'
    verbose_name = "QUOREM DB"
    default_auto_field = "django.db.models.BigAutoField"
