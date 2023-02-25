from main import models as main_models
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.http.response import Http404
from contextlib import suppress

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


def is_actual_subscription(telegram_id: str) -> bool:
    try:
        
        client = main_models.Client.objects.get(person__telegram_id=telegram_id)
        last_subscription = client.subscriptions.last()
        if last_subscription:
            return last_subscription.is_actual()
        return False
    except (main_models.Client.DoesNotExist,):
        return False


def is_client_phone(telegram_id: str) -> bool:  ## TODO !!!Может обозвать is_person_phone()?
    ### запрос приходит когда клиента вообще еще нет в базе пока закомментировал
    # person = main_models.Person.objects.get(telegram_id=telegram_id)
    #
    # return True if person.phone else False
    pass


def update_client_phone(telegram_id: str,
                        phonenumber: str) -> None:

    main_models.Person.objects.filter(telegram_id=telegram_id).update(phone=phonenumber)


def create_request(telegram_id: str,
                   message: str):
    ### TODO что имеется ввиду?
    return


def get_tariffs() -> QuerySet:
    return main_models.Tariff.objects.all()


def get_tariff(tariff_id: str):
    return main_models.Tariff.objects.get(id=int(tariff_id))


def create_subscription(telegram_id: str, tariff_id:str, payment_id: str):
    client = main_models.Client.objects.get(person__telegram_id=telegram_id)
    tariff = main_models.Tariff.objects.get(id=tariff_id)

    main_models.ClientSubscription.objects.create(
        client=client,
        tariff=tariff,
        payment_id=payment_id
    )

def create_contractor(*args, **kwargs):
    pass