from django.contrib import admin
from main.models import Order, ExampleOrder


@admin.register(ExampleOrder)
class RestaurantAdmin(admin.ModelAdmin):
    pass
