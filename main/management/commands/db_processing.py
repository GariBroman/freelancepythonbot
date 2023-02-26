from textwrap import dedent
from main import models as main_models
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.http.response import Http404
from contextlib import suppress

import main.management.commands.messages as messages

class EntityNotFoundError(Exception):
    def __init__(self, message: str = 'Сущность не найдена'):
        self.message = message

    def __str__(self):
        return self.message 


def get_role(telegram_id):
    try:
        person = get_object_or_404(main_models.Person, telegram_id=telegram_id)
        with suppress((main_models.Person.contractors.RelatedObjectDoesNotExist,
                       main_models.Person.owners.RelatedObjectDoesNotExist,
                       main_models.Person.managers.RelatedObjectDoesNotExist)):
            if person.clients:
                return 'client'
            elif person.contractors:
                return 'contractor'
            elif person.owners:
                return 'owner'
            elif person.managers:
                return 'manager'

    except Http404:
        return 'visitor'


def create_person(telegram_id: int,
                  username: str,
                  phonenumber: str) -> None:

    person, _ = main_models.Person.objects.update_or_create(
        telegram_id=telegram_id, defaults={'name': username, 'phone': phonenumber}
    )


def create_client(telegram_id: str) -> None:
    person = main_models.Person.objects.get(telegram_id=telegram_id)
    main_models.Client.objects.get_or_create(person=person)


def create_contractor(telegram_id: str, comment: str) -> None:
    person = main_models.Person.objects.get(telegram_id=telegram_id)
    main_models.Contractor.objects.get_or_create(person=person, comment=comment)


def get_client(telegram_id: str):
    return main_models.Client.objects.get(person__telegram_id=telegram_id)


def get_contractor(telegram_id: str):
    return main_models.Contractor.objects.get(person__telegram_id=telegram_id)


def is_actual_subscription(telegram_id: str) -> bool:
    try:
        
        client = main_models.Client.objects.get(person__telegram_id=telegram_id)
        last_subscription = client.subscriptions.last()
        if last_subscription:
            return last_subscription.is_actual()
        return False
    except (main_models.Client.DoesNotExist,):
        return False


def is_client_phone(telegram_id: str) -> bool:  # TODO !!!Может обозвать is_person_phone()?
    # запрос приходит когда клиента вообще еще нет в базе пока закомментировал
    # person = main_models.Person.objects.get(telegram_id=telegram_id)
    #
    # return True if person.phone else False
    pass


def update_client_phone(telegram_id: str,
                        phonenumber: str) -> None:

    main_models.Person.objects.filter(telegram_id=telegram_id).update(phone=phonenumber)


def get_tariffs() -> QuerySet:
    return main_models.Tariff.objects.all()


def get_tariff(tariff_id: str):
    return main_models.Tariff.objects.get(id=int(tariff_id))


def create_subscription(telegram_id: str, tariff_id: str, payment_id: str):
    client = main_models.Client.objects.get(person__telegram_id=telegram_id)
    tariff = main_models.Tariff.objects.get(id=tariff_id)

    main_models.ClientSubscription.objects.create(
        client=client,
        tariff=tariff,
        payment_id=payment_id
    )


def create_order(telegram_id: str, description: str):
    subscription = main_models.Client.objects.get(person__telegram_id=telegram_id).subscriptions.last()

    main_models.Order.objects.create(
        subscription=subscription,
        description=description
    )


def get_current_client_orders(telegram_id: int) -> list[dict]:
    client = main_models.Client.objects.get(person__telegram_id=telegram_id)

    return client.get_current_orders()


def is_available_request(telegram_id: int) -> bool:
    client = main_models.Client.objects.get(person__telegram_id=telegram_id)

    return client.is_new_request_available()


def get_order(telegram_id: str, order_id):
    client = main_models.Client.objects.get(person__telegram_id=telegram_id)
    order = main_models.Order.objects.get(id=order_id)

    if order.subscription in client.subscriptions.all():
        return order


def get_client_subscription_info(telegram_id: int) -> str or None:
    subscription = get_client(telegram_id=telegram_id).subscriptions.last()
    if subscription:
        return subscription.info_subscription()


def can_see_contractor_contacts(telegram_id: int) -> bool:
    subscription = get_client(telegram_id=telegram_id).subscriptions.last()
    if subscription:
        return subscription.tariff.contractor_contacts_availability


def create_comment_from_client(order_id, comment: str):
    order = main_models.Order.objects.get(id=order_id)
    main_models.OrderComments.objects.create(
        order=order,
        from_client=True,
        comment=comment
    )


def create_comment_from_contractor(order_id, comment: str):
    order = main_models.Order.objects.get(id=order_id)
    main_models.OrderComments.objects.create(
        order=order,
        from_contractor=True,
        comment=comment
    )

def get_order_contractor_contact(order_id: str) -> dict:
    order = main_models.Order.objects.get(id=order_id)
    if not order.contractor:
        raise EntityNotFoundError(messages.CONTRACTOR_NOT_FOUND)
    return {
        'first_name': order.contractor.person.name,
        'phone_number': order.contractor.person.phone,
        'user_id': order.contractor.person.telegram_id
    }