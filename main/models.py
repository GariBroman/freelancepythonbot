from django.db import models
from django.utils.timezone import now, timedelta
from phonenumber_field.modelfields import PhoneNumberField
from django.core.validators import MinValueValidator


class Person(models.Model):
    name = models.CharField('Name', max_length=200)
    phone = PhoneNumberField(verbose_name='Номер телефона', blank=True, db_index=True)
    telegram_id = models.SmallIntegerField('Телеграм ID', unique=True)

    class Meta:
        verbose_name = 'контакты пользователя'
        verbose_name_plural = 'контакты пользователей'

    def __str__(self):
        return f'{self.name} ({self.phone})'


class Client(models.Model):
    person = models.ForeignKey(
        Person,
        verbose_name='Заказчик',
        related_name='clients',
        on_delete=models.PROTECT
    )

    class Meta:
        verbose_name = 'заказчик'
        verbose_name_plural = 'заказчики'

    def __str__(self):
        return f'{self.person.name} ({self.person.phone})'

    def is_new_request_available(self):
        return self.subscriptions.last().orders_left() > 0


class Owner(models.Model):
    person = models.ForeignKey(
        Person,
        verbose_name='Администратор',
        related_name='owners',
        on_delete=models.PROTECT
    )

    class Meta:
        verbose_name = 'администратор'
        verbose_name_plural = 'администратор'

    def __str__(self):
        return f'{self.person.name} ({self.person.phone})'


class Contractor(models.Model):
    person = models.ForeignKey(
        Person,
        verbose_name='Подрядчик',
        related_name='contractors',
        on_delete=models.PROTECT
    )

    class Meta:
        verbose_name = 'подрядчик'
        verbose_name_plural = 'подрядчики'

    def __str__(self):
        return f'{self.person.name} ({self.person.phone})'


class Manager(models.Model):
    person = models.ForeignKey(
        Person,
        verbose_name='менеджер',
        related_name='managers',
        on_delete=models.PROTECT
    )

    class Meta:
        verbose_name = 'менеджер'
        verbose_name_plural = 'менеджеры'

    def __str__(self):
        return f'{self.person.name} ({self.person.phone})'


class Tariff(models.Model):
    title = models.CharField('Название тарифа', max_length=20)
    orders_limit = models.IntegerField('Лимит заявок в месяц')
    price = models.DecimalField(
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
        Client,
        verbose_name='Клиент',
        related_name='subscriptions',
        on_delete=models.PROTECT
    )
    contractor = models.ForeignKey(
        Contractor,
        verbose_name='Подрядчик',
        related_name='subscriptions',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    tariff = models.ForeignKey(
        Tariff,
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
        return self.tariff.orders_limit - len(self.client.orders.all())

    def expired_at(self):
        return self.started_at + self.tariff.validity

    def is_actual(self):
        return now() <= self.started_at + self.tariff.validity


class Order(models.Model):  # TODO проверить почему нет Client в заказе
    client = models.ForeignKey(
        Client,
        related_name='orders',
        verbose_name='Подписка',
        on_delete=models.PROTECT
    )
    contractor = models.ForeignKey(
        Contractor,
        related_name='orders',
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
        return f'[{self.client.person.name}] {self.description[:50]} -> {self.contractor.person.name}'


class OrderComments(models.Model):
    order = models.ForeignKey(
        Order,
        verbose_name='Order',
        related_name='comments',
        on_delete=models.PROTECT
    )
    from_client = models.BooleanField('Комментарий клиента', default=False)
    from_contractor = models.BooleanField('Комментарий клиента', default=False)
    comment = models.TextField('Comment', blank=True)
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
