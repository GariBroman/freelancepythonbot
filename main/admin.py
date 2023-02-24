from django.contrib import admin
from main.models import (
    Order, ExampleOrder, Tariff, ClientSubscription, OrderComments, Person
)


class OrderCommentsInline(admin.TabularInline):
    model = OrderComments
    extra = 0


class ClientSubscriptionInline(admin.TabularInline):
    fk_name = 'client'
    model = ClientSubscription
    extra = 0


@admin.register(ExampleOrder)
class ExampleOrderAdmin(admin.ModelAdmin):
    pass


@admin.register(Tariff)
class TariffAdmin(admin.ModelAdmin):
    pass


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', )
    inlines = [
        OrderCommentsInline
    ]


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    inlines = [
        ClientSubscriptionInline
    ]


@admin.register(ClientSubscription)
class ClientSubscriptionAdmin(admin.ModelAdmin):
    pass
