from django.core.management.base import BaseCommand
from main.models import ExampleOrder, Tariff, ServiceCategory, Service, Contractor
from django.utils.timezone import timedelta
from django.db.utils import IntegrityError


TARIFF_ITEMS = [
    {
        'title': 'Эконом',
        'orders_limit': 5,
        'answer_delay': timedelta(hours=24),
        'price': 200,
    },
    {
        'title': 'Стандарт',
        'orders_limit': 15,
        'answer_delay': timedelta(hours=1),
        'personal_contractor_available': True,
        'price': 400,
    },
    {
        'title': 'VIP',
        'orders_limit': 60,
        'answer_delay': timedelta(hours=1),
        'contractor_contacts_availability': True,
        'price': 600,
    },
]

EXAMPLE_TEXT = [
    'Здравствуйте, нужно добавить в интернет - магазин фильтр товаров по цвету',
    'Здравствуйте, нужно выгрузить товары с сайта в Excel - таблице',
    'Здравствуйте, нужно загрузить 450 SKU на сайт из Excel таблицы',
    'Здравствуйте, хочу провести на сайте акцию, хочу разместить баннер и добавить функционал, чтобы впридачу к акционным товарам выдавался приз',
]

def create_service_categories():
    """Создает начальные категории услуг"""
    categories = [
        {
            'name': 'Красота, здоровье, психология',
            'description': 'Услуги в сфере красоты, здоровья и психологической помощи'
        },
        {
            'name': 'Разработка, Продвижение, Дизайн',
            'description': 'IT-услуги, разработка сайтов, приложений, дизайн и маркетинг'
        },
        {
            'name': 'Другое',
            'description': 'Прочие услуги'
        }
    ]
    
    for category_data in categories:
        ServiceCategory.objects.get_or_create(
            name=category_data['name'],
            defaults={'description': category_data['description']}
        )
    
    print(f'Created {len(categories)} service categories')


def create_test_services():
    """Создает тестовые услуги для демонстрации"""
    # Проверяем, есть ли категории
    categories = ServiceCategory.objects.all()
    if not categories.exists():
        print("Нет категорий услуг. Сначала создайте категории.")
        return
    
    # Проверяем, есть ли подрядчики
    contractors = Contractor.objects.all()
    if not contractors.exists():
        print("Нет подрядчиков. Сначала создайте подрядчиков.")
        return
    
    # Тестовые услуги для категории "Красота, здоровье, психология"
    beauty_category = ServiceCategory.objects.get(name="Красота, здоровье, психология")
    beauty_services = [
        {
            "title": "Консультация психолога",
            "description": "Индивидуальная консультация психолога по личным вопросам. Помощь в решении проблем, связанных со стрессом, тревогой, депрессией.",
            "price": 2500.00
        },
        {
            "title": "Маникюр с покрытием гель-лаком",
            "description": "Профессиональный маникюр с покрытием гель-лаком. Стойкое покрытие до 3 недель.",
            "price": 1500.00
        },
        {
            "title": "Массаж спины",
            "description": "Профессиональный массаж спины для снятия напряжения и улучшения самочувствия.",
            "price": 2000.00
        }
    ]
    
    # Тестовые услуги для категории "Разработка, Продвижение, Дизайн"
    dev_category = ServiceCategory.objects.get(name="Разработка, Продвижение, Дизайн")
    dev_services = [
        {
            "title": "Разработка сайта-визитки",
            "description": "Создание современного сайта-визитки для вашего бизнеса. Адаптивный дизайн, SEO-оптимизация.",
            "price": 15000.00
        },
        {
            "title": "Дизайн логотипа",
            "description": "Разработка уникального логотипа для вашего бренда. 3 варианта на выбор, неограниченное количество правок.",
            "price": 5000.00
        },
        {
            "title": "Настройка рекламы в Instagram",
            "description": "Профессиональная настройка таргетированной рекламы в Instagram для привлечения целевой аудитории.",
            "price": 7000.00
        }
    ]
    
    # Тестовые услуги для категории "Другое"
    other_category = ServiceCategory.objects.get(name="Другое")
    other_services = [
        {
            "title": "Репетитор по английскому языку",
            "description": "Индивидуальные занятия по английскому языку для взрослых и детей. Подготовка к экзаменам, разговорная практика.",
            "price": 1200.00
        },
        {
            "title": "Выгул собак",
            "description": "Профессиональный выгул собак. Прогулки в парке, игры, социализация.",
            "price": 500.00
        }
    ]
    
    # Создаем услуги для каждой категории
    services_created = 0
    
    # Распределяем подрядчиков по категориям
    contractors_list = list(contractors)
    
    # Создаем услуги для категории "Красота, здоровье, психология"
    for i, service_data in enumerate(beauty_services):
        contractor = contractors_list[i % len(contractors_list)]
        try:
            Service.objects.get_or_create(
                title=service_data["title"],
                contractor=contractor,
                defaults={
                    "description": service_data["description"],
                    "price": service_data["price"],
                    "category": beauty_category
                }
            )
            services_created += 1
        except IntegrityError:
            pass
    
    # Создаем услуги для категории "Разработка, Продвижение, Дизайн"
    for i, service_data in enumerate(dev_services):
        contractor = contractors_list[(i + 1) % len(contractors_list)]
        try:
            Service.objects.get_or_create(
                title=service_data["title"],
                contractor=contractor,
                defaults={
                    "description": service_data["description"],
                    "price": service_data["price"],
                    "category": dev_category
                }
            )
            services_created += 1
        except IntegrityError:
            pass
    
    # Создаем услуги для категории "Другое"
    for i, service_data in enumerate(other_services):
        contractor = contractors_list[(i + 2) % len(contractors_list)]
        try:
            Service.objects.get_or_create(
                title=service_data["title"],
                contractor=contractor,
                defaults={
                    "description": service_data["description"],
                    "price": service_data["price"],
                    "category": other_category
                }
            )
            services_created += 1
        except IntegrityError:
            pass
    
    print(f"Создано {services_created} тестовых услуг")


class Command(BaseCommand):
    help = "Загрузка начальных данных"

    def handle(self, *args, **kwargs):

        if not ExampleOrder.objects.all():
            ExampleOrder.objects.bulk_create([ExampleOrder(text=text) for text in EXAMPLE_TEXT])

        if not Tariff.objects.all():
            tariffs = [Tariff(**item) for item in TARIFF_ITEMS]
            Tariff.objects.bulk_create(tariffs)

        create_service_categories()
        create_test_services()

