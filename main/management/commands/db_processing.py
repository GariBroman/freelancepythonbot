from django.db.models import QuerySet, Sum
from django.utils.timezone import datetime, timedelta, now
from django.db.utils import IntegrityError

import main.management.commands.messages as messages

from main import models as main_models


class EntityNotFoundError(Exception):
    def __init__(self, message: str = 'Сущность не найдена'):
        self.message = message

    def __str__(self):
        return self.message 
    

def fetch_start_end_of_month(date: datetime = None) -> tuple[datetime, datetime]:
    point = date or datetime.now().date()
    # if date:
    #     point = date
    # else:
    #     point = datetime.now().date()

    start_month = datetime(day=1, month=point.month, year=point.year)
    next_month = datetime(day=28, month=point.month, year=point.year) + timedelta(days=4)
    end_month = datetime(day=1, month=next_month.month, year=next_month.year)
    # maybe just return start_month?

    return start_month, end_month


def get_person(telegram_id: int) -> main_models.Person | None:
    try:
        return main_models.Person.objects.get(telegram_id=telegram_id)
    except main_models.Person.DoesNotExist:
        return


def is_contractor(telegram_id: int) -> bool:
    try:
        main_models.Contractor.objects.get(person__telegram_id=telegram_id, active=True)
        return True
    except main_models.Contractor.DoesNotExist:
        return False


def create_person(telegram_id: int,
                  username: str,
                  phonenumber: str) -> None:
    main_models.Person.objects.update_or_create(
        telegram_id=telegram_id,
        defaults={'name': username, 'phone': phonenumber}
    )


def create_client(telegram_id: int) -> None:
    person = main_models.Person.objects.get(telegram_id=telegram_id)
    main_models.Client.objects.get_or_create(person=person)


def create_contractor(telegram_id: int, comment: str) -> main_models.Contractor:
    person = main_models.Person.objects.get(telegram_id=telegram_id)
    try:
        contractor = main_models.Contractor.objects.get_or_create(person=person, comment=comment)
    except IntegrityError:
        contractor = main_models.Contractor.objects.get(person=person)
    return contractor


def get_client(telegram_id: int) -> main_models.Client:
    return main_models.Client.objects.get(person__telegram_id=telegram_id)


def get_contractor(telegram_id: int) -> main_models.Contractor:
    return main_models.Contractor.objects.get(person__telegram_id=telegram_id)


def is_actual_subscription(telegram_id: int) -> bool:
    try:
        client = main_models.Client.objects.get(person__telegram_id=telegram_id)
        last_subscription = client.subscriptions.last()
        if last_subscription:
            return last_subscription.is_actual()
        return False
    except (main_models.Client.DoesNotExist,):
        return False


def update_client_phone(telegram_id: int,
                        phonenumber: str) -> None:
    main_models.Person.objects.filter(telegram_id=telegram_id).update(phone=phonenumber)


def get_tariffs() -> QuerySet:
    return main_models.Tariff.objects.all()


def get_tariff(tariff_id: str) -> main_models.Tariff:
    return main_models.Tariff.objects.get(id=int(tariff_id))


def create_subscription(telegram_id: int,
                        tariff_id: str,
                        payment_id: str) -> main_models.ClientSubscription:
    client = main_models.Client.objects.get(person__telegram_id=telegram_id)
    tariff = main_models.Tariff.objects.get(id=tariff_id)

    subscription = main_models.ClientSubscription.objects.create(
        client=client,
        tariff=tariff,
        payment_id=payment_id
    )
    return subscription

def create_order(telegram_id: int, description: str) -> main_models.Order:
    subscription = main_models.Client.objects.get(person__telegram_id=telegram_id) \
        .subscriptions.last()
    order = main_models.Order.objects.create(
        subscription=subscription,
        description=description
    )
    return order


def get_current_client_orders(telegram_id: int) -> list[dict]:
    client = main_models.Client.objects.get(person__telegram_id=telegram_id)
    return client.get_current_orders()


def is_available_request(telegram_id: int) -> bool:
    client = main_models.Client.objects.get(person__telegram_id=telegram_id)
    return client.is_new_request_available()


def get_order(telegram_id: int, order_id: int) -> main_models.Order:
    # client = main_models.Client.objects.get(person__telegram_id=telegram_id)
    # order = main_models.Order.objects.get(id=order_id)
    # if order.subscription in client.subscriptions.all():
    #     return order
    order = main_models.Order.objects.get(
        id=order_id,
        subscription__client__person__telegram_id=telegram_id
    )
    return order


def get_client_subscription_info(telegram_id: int) -> str or None:
    subscription = get_client(telegram_id=telegram_id).subscriptions.last()
    if subscription and subscription.is_actual():
        return subscription.info_subscription()


def can_see_contractor_contacts(telegram_id: int) -> bool:
    subscription = get_client(telegram_id=telegram_id).subscriptions.last()
    if subscription and subscription.is_actual():
        return subscription.tariff.contractor_contacts_availability


def create_comment_from_client(order_id: int,
                               comment: str) -> tuple[main_models.Order, main_models.OrderComments]:
    order = main_models.Order.objects.get(id=order_id)
    comment = main_models.OrderComments.objects.create(
        order=order,
        author='client',
        comment=comment
    )
    return order, comment


def create_comment_from_contractor(order_id: int, comment: str) -> None:
    order = main_models.Order.objects.get(id=order_id)
    main_models.OrderComments.objects.create(
        order=order,
        author='contractor',
        comment=comment
    )


def get_order_contractor_contact(order_id: int) -> dict:
    order = main_models.Order.objects.get(id=order_id)
    if not order.contractor:
        raise EntityNotFoundError(messages.CONTRACTOR_NOT_FOUND)
    return {
        'first_name': order.contractor.person.name,
        'phone_number': order.contractor.person.phone,
        'user_id': order.contractor.person.telegram_id
    }


def create_client_order_complaint(order_id: int,
                                  complaint: str) -> tuple[main_models.Order, main_models.Complaint]:
    order = main_models.Order.objects.get(id=order_id)
    complaint = main_models.Complaint.objects.create(
        order=order,
        complaint=complaint
    )
    return order, complaint


def get_contractor_current_orders(telegram_id: int) -> list[dict[str, int|str]]:
    contractor = get_contractor(telegram_id=telegram_id)
    orders = main_models.Order.objects.filter(contractor=contractor).filter(finished_at__isnull=True). \
        filter(declined=False).order_by('created_at')
    current_orders = [
        {'id': order.id, 'display': order.short_display()} for order in orders
    ]
    return current_orders


def get_contractor_available_orders(telegram_id: int) -> list[dict[str, int|str]]:
    orders = main_models.Order.objects.all().order_by('created_at')
    available_orders = [
        {'id': order.id, 'display': order.short_display()} for order in orders if order.is_available_order()
    ]
    return available_orders


def display_contractor_salary(telegram_id: int) -> str:
    contractor = get_contractor(telegram_id=telegram_id)

    start_period, end_period = fetch_start_end_of_month()
    filter_args = {
        'contractor': contractor,
        'finished_at__isnull': False,
        'finished_at__gte': start_period,
        'finished_at__lt': end_period
    }
    query = contractor.orders.filter(**filter_args).aggregate(Sum('salary'))

    return f'Всего вы выполнили заказов на {query["salary__sum"]} руб.'


def display_order_info(order_id: int) -> str:
    order = main_models.Order.objects.get(id=order_id)

    return order.display()


def set_estimate_datetime(order_id: int, estimate_datetime: datetime) -> main_models.Order:
    order = main_models.Order.objects.get(id=order_id)
    order.estimated_time=estimate_datetime
    order.save()
    return order


def close_order(order_id: int) -> None: # TODO return ссылка на заказ в админке!
    order = main_models.Order.objects.get(id=order_id)
    order.finished_at=now()
    order.save()


def get_managers_telegram_ids() -> tuple[int]:
    managers = main_models.Manager.objects.filter(active=True)

    return tuple(manager.person.telegram_id for manager in managers)

