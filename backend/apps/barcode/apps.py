from django.apps import AppConfig


class BarcodeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.barcode"
    label = "barcode"
    verbose_name = "Barcode"
