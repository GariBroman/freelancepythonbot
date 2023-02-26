from django.contrib import admin
from django import forms
from django.db.models import Sum
from django.db import models
from django.forms import Textarea
from django.utils import timezone
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
    Person,
    Complaint
)


import nested_admin


class OrderCommentsInline(admin.TabularInline):
    model = OrderComments
    fields = ('author', 'comment', 'created_at')
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 2, 'cols': 60})},
    }
    readonly_fields = ('created_at',)
    extra = 0


class OrderSubscriptionInline(nested_admin.NestedTabularInline):
    fk_name = 'subscription'
    fields = [('contractor', 'description'), 'finished_at']
    formfield_overrides = {
        models.TextField: {'widget': Textarea(attrs={'rows': 2, 'cols': 50})},
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


class OrderContractorInline(admin.StackedInline):
    fk_name = 'contractor'
    fields = (('subscription', 'description', 'salary'), ('take_at', 'finished_at'))
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
    list_display = (
        'title', 
        'orders_limit', 
        'price',  
        'contractor_contacts_availability', 
        'personal_contractor_available'
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    readonly_fields = ('created_at', )
    list_display = ('get_client', 'contractor', 'created_at', 'take_at', 'estimated_time', 'declined')
    search_fields = ('contractor__person__name', 'subscription__client__person__name')
    inlines = [
        OrderCommentsInline
    ]
    list_filter = ('created_at', 'finished_at', 'estimated_time', 'declined', 'contractor', 'subscription__client')
    
    @admin.display(ordering='subscription__client', description='client')
    def get_client(self, obj):
        return obj.subscription.client
    actions = ['get_monthly_salaries']  

    @admin.action(description='Get monthly salaries')
    def get_monthly_salaries(modeladmin, request, queryset):
        payments = queryset.filter(finished_at__gte=timezone.now() - timezone.timedelta(days=30)) \
            .select_related('contractor__person').values('contractor__person__telegram_id').annotate(total_salary=Sum('salary'))
        print(payments)
        with open("example.txt", "w") as f:
            f.write(str(payments))
        return payments    


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    search_fields = ('name', 'phone', 'telegram_id')
    list_display = ('name', 'telegram_id', 'phone')


@admin.register(Client)
class ClientAdmin(nested_admin.NestedModelAdmin):
    inlines = [
        ClientSubscriptionInline,
    ]
    list_display = ('__str__', 'get_telegram_id')
    search_fields = ('person__name', 'person__phone', 'person__telegram_id')

    @admin.display(ordering='person__telegram_id', description='telegram_id')
    def get_telegram_id(self, obj):
        return obj.person.telegram_id
    

@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    pass


@admin.register(Manager)
class ManagerAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'get_telegram_id', 'active')
    search_fields = ('person__name', 'person__phone', 'person__telegram_id')

    @admin.display(ordering='person__telegram_id', description='telegram_id')
    def get_telegram_id(self, obj):
        return obj.person.telegram_id


@admin.register(Contractor)
class ContractorAdmin(admin.ModelAdmin):
    inlines = [
        OrderContractorInline
    ]
    list_display = ('__str__', 'get_telegram_id', 'active')
    search_fields = ('person__name', 'person__phone', 'person__telegram_id')

    @admin.display(ordering='person__telegram_id', description='telegram_id')
    def get_telegram_id(self, obj):
        return obj.person.telegram_id


@admin.register(ClientSubscription)
class ClientSubscriptionAdmin(admin.ModelAdmin):
    inlines = [
        OrderSubscriptionInline
    ]
    list_display = ('client', 'orders_left', 'tariff', 'contractor')
    search_fields = ('client__person__name', 'contractor__person__name')


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ('order', 'complaint', 'created_at', 'closed_at')
    search_fields = ('order', )
    list_filter = ('created_at', )
