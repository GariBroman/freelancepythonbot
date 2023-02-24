from django.core.management.base import BaseCommand
from main.models import ExampleOrder, Tariff
from django.utils.timezone import timedelta


TARIFF_ITEMS = [
    {
        'title': 'Эконом',
        'orders_limit': 5,
        'answer_delay': timedelta(hours=24),
        'subscription_price': 4000,
    },
    {
        'title': 'Стандарт',
        'orders_limit': 15,
        'answer_delay': timedelta(hours=1),
        'personal_contractor_available': True,
        'subscription_price': 9000,
    },
    {
        'title': 'VIP',
        'orders_limit': 60,
        'answer_delay': timedelta(hours=1),
        'contractor_contacts_availability': True,
        'subscription_price': 40000,
    },
]

EXAMPLE_TEXT = [
    'Здравствуйте, нужно добавить в интернет - магазин фильтр товаров по цвету',
    'Здравствуйте, нужно выгрузить товары с сайта в Excel - таблице',
    'Здравствуйте, нужно загрузить 450 SKU на сайт из Excel таблицы',
    'Здравствуйте, хочу провести на сайте акцию, хочу разместить баннер и добавить функционал, чтобы впридачу к акционным товарам выдавался приз',
]

class Command(BaseCommand):
    help = "Загрузка начальных данных"

    def handle(self, *args, **kwargs):

        if not ExampleOrder.objects.all():
            ExampleOrder.objects.bulk_create([ExampleOrder(text=text) for text in EXAMPLE_TEXT])

        if not Tariff.objects.all():
            tariffs = [Tariff(**item) for item in TARIFF_ITEMS]
            Tariff.objects.bulk_create(tariffs)

