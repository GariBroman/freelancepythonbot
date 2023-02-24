from django.db import models
from django.utils.timezone import now, timedelta
from phonenumber_field.modelfields import PhoneNumberField
from django.core.validators import MinValueValidator


class Person(models.Model):
    ROLE = (
        ('client', 'Клиент'),
        ('contractor', 'Подрядчик'),
        ('admin', 'Заказчик проекта'),
        ('manager', 'Менеджер')
    )
    name = models.CharField('Name', max_length=200)
    telegram_id = models.SmallIntegerField('Телеграм ID')
    role = models.CharField(verbose_name='Тип пользователя', max_length=10, choices=ROLE)
    phonenumber = PhoneNumberField(verbose_name='Номер телефона', blank=True, db_index=True)

    class Meta:
        verbose_name = 'пользователь'
        verbose_name_plural = 'пользователи'

    def __str__(self):
        return f'{self.name} ({self.role})'

    def is_new_request_available(self):
        return self.client_subscriptions.last().orders_left() > 0
    

class Tariff(models.Model):
    title = models.CharField('Название тарифа', max_length=20)
    orders_limit = models.IntegerField('Лимит заявок в месяц')
    subscription_price = models.DecimalField(
        'стоимость подписки',
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    validity = models.DurationField('Срок действия', default=timedelta(days=30))
    answer_delay = models.DurationField('Время ответа на заявку')
    contractor_contacts_availability = models.BooleanField('Возможность видеть контакты подрядчика', default=False)
    personal_contractor_available = models.BooleanField('Закрепить за собой подрядчика', default=False)

    class Meta:
        verbose_name = 'тариф'
        verbose_name_plural = 'тарифы'

    def __str__(self):
        return self.title


class ClientSubscription(models.Model):
    client = models.ForeignKey(
        'Person',
        verbose_name='Клиент',
        related_name='client_subscriptions',
        on_delete=models.PROTECT
    )
    contractor = models.ForeignKey(
        'Person',
        verbose_name='Подрядчик',
        related_name='contractor_subscriptions',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    tariff = models.ForeignKey(
        'Tariff',
        verbose_name='Тариф',
        related_name='subscriptions',
        on_delete=models.PROTECT
    )
    started_at = models.DateTimeField('Старт подписки', auto_now_add=True)
    
    class Meta:
        verbose_name = 'договор клиента'
        verbose_name_plural = 'договора клиентов'

    def __str__(self):
        return f'{self.client}, {self.tariff} Остаток заявок: {self.orders_left()}'

    def orders_left(self):
        return self.tariff.orders_limit - len(self.orders.all())

    def expired_at(self):
        return self.started_at + self.tariff.validity

    def is_actual(self):
        return now() <= self.started_at + self.tariff.validity


class Order(models.Model): ## TODO проверить почему нет Client в заказе
    subscription = models.ForeignKey(
        'ClientSubscription',
        related_name='orders',
        verbose_name='Подписка',
        on_delete=models.PROTECT
    )
    contractor = models.ForeignKey(
        Person,
        related_name='contractor_orders',
        verbose_name='подрядчик',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    salary = models.DecimalField(
        'стоимость работ',
        max_digits=8,
        decimal_places=2,
        default=300,
        validators=[MinValueValidator(0)]
    )
    description = models.TextField('Текст заявки')
    created_at = models.DateTimeField('Заказ создан', auto_now_add=True, db_index=True)
    take_at = models.DateTimeField('Взят в работу', null=True, blank=True, db_index=True)
    finished_at = models.DateTimeField('Заказ выполнен', null=True, blank=True, db_index=True)
    
    class Meta:
        verbose_name = 'заказ'
        verbose_name_plural = 'заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.subscription.client}] {self.description[:50]} -> {self.contractor}'


class OrderComments(models.Model):
    order = models.ForeignKey(
        'Order',
        verbose_name='Order',
        related_name='comments',
        on_delete=models.PROTECT
    )
    author = models.ForeignKey(
        'Person',
        verbose_name='Author',
        related_name='comments',
        on_delete=models.PROTECT
    )
    comment = models.TextField('Comment')
    created_at = models.DateTimeField('Created at', auto_now_add=True)
    
    def __str__(self):
        return f'{self.comment[:100]}...'


class ExampleOrder(models.Model):
    text = models.CharField('Текст заявки', max_length=200)

    class Meta:
        verbose_name = 'пример заявки'
        verbose_name_plural = 'примеры заявок'

    def __str__(self):
        return self.text
