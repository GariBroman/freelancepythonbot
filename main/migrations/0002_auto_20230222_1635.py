from django.db import migrations


def initial_tariff(apps, scheme_editor):
    tariff_items = [
        {
            'name': 'Эконом',
            'limit_orders': 5,
            'limit_time_answer': 24
        },
        {
            'name': 'Стандарт',
            'limit_orders': 15,
            'limit_time_answer': 1,
            'can_attach_contractor': True
        },
        {
            'name': 'VIP',
            'limit_orders': 60,
            'limit_time_answer': 1,
            'can_see_contractor': True
        },
    ]
    Tariff = apps.get_model('main', 'Tariff')
    tariffs = [Tariff(**item) for item in tariff_items]
    Tariff.objects.bulk_create(tariffs)


def initial_examples_text(apps, scheme_editor):
    example_text = [
        'Здравствуйте, нужно добавить в интернет - магазин фильтр товаров по цвету',
        'Здравствуйте, нужно выгрузить товары с сайта в Excel - таблице',
        'Здравствуйте, нужно загрузить 450 SKU на сайт из Excel таблицы',
        'Здравствуйте, хочу провести на сайте акцию, хочу разместить баннер и добавить функционал, чтобы впридачу к акционным товарам выдавался приз',
    ]
    ExampleOrder = apps.get_model('main', 'ExampleOrder')
    ExampleOrder.objects.bulk_create([ExampleOrder(text=text) for text in example_text])


class Migration(migrations.Migration):

    dependencies = [
        ('main', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(initial_examples_text),
        migrations.RunPython(initial_tariff),
    ]
