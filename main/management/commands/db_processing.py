from main import models as main_models
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django.http.response import Http404


def get_role(telegram_id):
    try:
        person = get_object_or_404(main_models.Person, telegram_id=telegram_id)
        if person.clients.all():
            return 'client'
        elif person.contractors.all():
            return 'contractor'
        elif person.owners.all():
            return 'owner'
        elif person.managers.all():
            return 'manager'

    except Http404:
        return 'visitor'


def create_client(telegram_id: str,
                  username: str,
                  role: str = 'client') -> None:

    person, _ = main_models.Person.objects.update_or_create(
        telegram_id=telegram_id, name=username, defaults={'telegram_id': telegram_id}
    )
    main_models.Client.objects.create(person=person)


def get_client(telegram_id: str):
    return main_models.Client.objects.get(person__telegram_id=telegram_id)


def is_actual_subscription(telegram_id: str) -> bool:
    ### TODO запрос приходит когда клиента вообще еще нет в базе пока закомментировал
    # client = main_models.Person.objects.get(telegram_id=telegram_id)
    #
    # return len([subscription.is_actual for subscription in client.client_subscriptions]) > 0
    pass

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
