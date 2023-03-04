from textwrap import dedent
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
    person = models.OneToOneField(
        Person,
        verbose_name='Клиент',
        related_name='clients',
        on_delete=models.PROTECT
    )

    class Meta:
        verbose_name = 'клиент'
        verbose_name_plural = 'клиенты'

    def __str__(self):
        return f'{self.person.name} ({self.person.phone})'

    def has_actual_subscription(self):
        if not self.subscriptions.last():
            return False
        return self.subscriptions.last().is_actual()

    def is_new_request_available(self):
        return self.subscriptions.last().orders_left() > 0

    def get_current_orders(self):
        return Order.objects.filter(subscription__client=self, finished_at=None, declined=False)


class Owner(models.Model):
    person = models.OneToOneField(
        Person,
        verbose_name='Администратор',
        related_name='owners',
        on_delete=models.PROTECT
    )
    active = models.BooleanField('Активность', default=False)

    class Meta:
        verbose_name = 'администратор'
        verbose_name_plural = 'администратор'

    def __str__(self):
        return f'{self.person.name} ({self.person.phone})'


class Contractor(models.Model):
    person = models.OneToOneField(
        Person,
        verbose_name='Подрядчик',
        related_name='contractors',
        on_delete=models.PROTECT
    )
    active = models.BooleanField('исполнитель утвержден', default=False)
    comment = models.TextField('заявка на утверждение', blank=True)

    class Meta:
        verbose_name = 'подрядчик'
        verbose_name_plural = 'подрядчики'

    def __str__(self):
        return f'{self.person.name} ({self.person.phone})'

    def get_current_orders(self) -> models.QuerySet:
        return self.orders.filter(
            finished_at__isnull=True,
            declined=False
        ).order_by('created_at')


class Manager(models.Model):
    person = models.OneToOneField(
        Person,
        verbose_name='менеджер',
        related_name='managers',
        on_delete=models.PROTECT
    )
    active = models.BooleanField('Активность', default=False)

    class Meta:
        verbose_name = 'менеджер'
        verbose_name_plural = 'менеджеры'

    def __str__(self):
        return f'{self.person.name} ({self.person.phone})'


class Tariff(models.Model):
    title = models.CharField('Название тарифа', max_length=20, unique=True)
    orders_limit = models.IntegerField('Лимит заявок в месяц')
    price = models.IntegerField(
        'стоимость подписки',
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

    def payment_description(self):
        return dedent(
            f"""
            Ответ на заявку в течении: {self.display_answer_delay()}
            Срок действия тарифа: {self.validity.total_seconds() // 86400} дн.
            """
        )

    def display_answer_delay(self) -> str:
        total_seconds = self.answer_delay.total_seconds()

        days = total_seconds // 86400
        remaining_hours = total_seconds % 86400
        remaining_minutes = remaining_hours % 3600
        hours = remaining_hours // 3600
        minutes = remaining_minutes // 60
        seconds = remaining_minutes % 60

        days_str = f'{days} дн. ' if days else ''
        hours_str = f'{hours} ч. ' if hours else ''
        minutes_str = f'{minutes} мин ' if minutes else ''
        seconds_str = f'{seconds} сек ' if seconds and not hours_str else ''

        return f'{days_str}{hours_str}{minutes_str}{seconds_str}'

    def display(self) -> str:
        return dedent(
            f"""
            {self.title}.
            {self.orders_limit} заявок в месяц.
            """
        )


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
    payment_id = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = 'подписка клиента'
        verbose_name_plural = 'подписки клиентов'

    def __str__(self):
        return f'{self.client}, {self.tariff} Остаток заявок: {self.orders_left()}'

    def orders_left(self):
        return self.tariff.orders_limit - len(self.orders.all())

    def expired_at(self):
        return self.started_at + self.tariff.validity

    def is_actual(self):
        return now() <= self.started_at + self.tariff.validity

    def info_subscription(self):
        info = dedent(
            f"""
            Тарифный план: {self.tariff.title}
            Доступных заявок: {self.orders_left()}
            Подписка закончится: {self.expired_at().strftime('%Y-%m-%d')}
            """
        )
        return info


class OrderManager(models.QuerySet):
    def get_availables(self):
        return self.filter(
            declined=False,
            contractor=None,
            take_at=None
        )


class Order(models.Model):
    subscription = models.ForeignKey(
        ClientSubscription,
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
    salary = models.IntegerField(
        'стоимость работ',
        default=20,
        validators=[MinValueValidator(0)]
    )
    description = models.TextField('Текст заявки')
    declined = models.BooleanField('Заявка отклонена', default=False)
    created_at = models.DateTimeField('Заказ создан', auto_now_add=True, db_index=True)
    take_at = models.DateTimeField('Взят в работу', null=True, blank=True, db_index=True)
    estimated_time = models.DateTimeField('Срок выполнения заказа', null=True, blank=True, db_index=True)
    finished_at = models.DateTimeField('Заказ выполнен', null=True, blank=True, db_index=True)

    objects = OrderManager.as_manager()

    class Meta:
        verbose_name = 'заказ'
        verbose_name_plural = 'заказы'
        ordering = ['-created_at']

    def __str__(self):
        contractor = self.contractor.person.name if self.contractor else ''
        return f'[{self.subscription.client.person.name}] {self.description[:50]} -> {contractor}'

    def is_available_order(self):
        if not self.declined and not self.contractor and not self.take_at:
            return True

    def is_taken_deadline(self):
        return now() > self.created_at + timedelta(self.subscription.tariff.answer_delay)

    def display(self) -> str:
        message = dedent(
            f"""
            {self.created_at.strftime('%Y-%m-%d')}
            {self.description[:50]}...
            Сроки выполнения: {self.estimated_time if self.estimated_time else 'производится оценка...'}
            Статус заявки: {'в работе' if self.contractor else 'Ожидает распределения'}
            """
        )
        return message


class OrderComments(models.Model):
    AUTHOR = (
        ('client', 'Клиент'),
        ('contactor', 'Подрядчик'),
        ('owner', 'Администратор'),
        ('manager', 'Менеджер'),
    )
    order = models.ForeignKey(
        Order,
        verbose_name='комментарий',
        related_name='comments',
        on_delete=models.PROTECT
    )
    author = models.CharField('Автор комментария', max_length=10, choices=AUTHOR, null=True, blank=True)
    comment = models.TextField('Comment', blank=True)
    created_at = models.DateTimeField('Created at', auto_now_add=True)

    def __str__(self):
        return f'[{self.author}] {self.comment[:100]}...'


class ExampleOrder(models.Model):
    text = models.CharField('Текст заявки', max_length=200)

    class Meta:
        verbose_name = 'пример заявки'
        verbose_name_plural = 'примеры заявок'

    def __str__(self):
        return self.text


class Complaint(models.Model):
    order = models.ForeignKey(
        Order,
        verbose_name='жалоба',
        related_name='complaints',
        on_delete=models.PROTECT
    )
    admin = models.ForeignKey(
        Owner,
        verbose_name='админ',
        related_name='complaints',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    manager = models.ForeignKey(
        Manager,
        verbose_name='менеджер',
        related_name='complaints',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    complaint = models.TextField('Текст жалобы', blank=True)
    answer = models.TextField('Ответ на жалобу', blank=True)
    created_at = models.DateTimeField('Жалоба подана', auto_now_add=True, db_index=True)
    closed_at = models.DateTimeField('Жалоба закрыта', null=True, blank=True, db_index=True)

    class Meta:
        verbose_name = 'жалоба'
        verbose_name_plural = 'жалобы'

    def __str__(self):
        return f'{self.created_at} - {self.complaint} -> {self.order}'
