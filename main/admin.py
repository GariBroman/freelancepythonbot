from django.contrib import admin
from main.models import Order, ExampleOrder, Tariff


@admin.register(ExampleOrder)
class ExampleOrderAdmin(admin.ModelAdmin):
    pass


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    pass


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    pass