from django.contrib import admin
from main.models import Order, ExampleOrder, Tariff, ClientSubscription, OrderComments, Person


@admin.register(ExampleOrder)
class ExampleOrderAdmin(admin.ModelAdmin):
    pass


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    pass


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    pass


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    pass


@admin.register(ClientSubscription)
class ClientSubscriptionAdmin(admin.ModelAdmin):
    pass
