from django.contrib import admin
from django import forms
from django.db import models
from django.forms import Textarea
from main.models import (
    Order, 
    ExampleOrder, 
    Tariff, 
    ClientSubscription, 
    OrderComments,
    Client, 
    Contractor, 
    Owner, 
    Manager, 
    Person
)

import nested_admin


class OrderCommentsInline(admin.TabularInline):
    model = OrderComments
    fields = ('created_at', 'comment')
    readonly_fields = ('created_at',)
    extra = 0


class OrderSubscriptionInline(nested_admin.NestedTabularInline):
    fk_name = 'subscription'
    fields = ('contractor', 'description')
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 2, 'cols': 60})},
    }
    model = Order
    extra = 0


class ClientSubscriptionInline(nested_admin.NestedTabularInline):
    fk_name = 'client'
    model = ClientSubscription
    extra = 0
    inlines = [
        OrderSubscriptionInline
    ]


class OrderContractorInline(admin.TabularInline):
    fk_name = 'contractor'
    fields = ('subscription', 'description')
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows':2, 'cols':40})},
    }
    model = Order
    extra = 0


class ExampleOrderModelForm(forms.ModelForm):
    text = forms.CharField(widget=forms.Textarea)

    class Meta:
        model = ExampleOrder
        fields = '__all__'


@admin.register(ExampleOrder)
class ExampleOrderAdmin(admin.ModelAdmin):
    form = ExampleOrderModelForm


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
    pass


@admin.register(Client)
class ClientAdmin(nested_admin.NestedModelAdmin):
    inlines = [
        ClientSubscriptionInline,
    ]


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    pass


@admin.register(Manager)
class ManagerAdmin(admin.ModelAdmin):
    pass


@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    inlines = [
        OrderContractorInline
    ]


@admin.register(ClientSubscription)
class ClientSubscriptionAdmin(admin.ModelAdmin):
    inlines = [
        OrderSubscriptionInline
    ]
