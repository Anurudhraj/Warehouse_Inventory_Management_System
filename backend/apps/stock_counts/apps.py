from django.apps import AppConfig


class StockCountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.stock_counts"
    label = "stock_counts"
    verbose_name = "Stock Counts"
