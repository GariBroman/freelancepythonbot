from main import models as main_models
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404


def get_role(telegram_id):
    person = get_object_or_404(main_models.Person, telegram_id=telegram_id)

    return person.role if person else 'visitor'


def create_client(telegram_id: str,
                  username: str,
                  role: str = 'client') -> None:

    main_models.Person.objects.update_or_create(
        telegram_id=telegram_id, name=username, role=role, defaults={'telegram_id': telegram_id}
    )


def get_client(telegram_id: str):
    return get_object_or_404(main_models.Person, telegram_id=telegram_id)


def is_actual_subscription(telegram_id: str) -> bool:
    client = main_models.Person.objects.get(telegram_id=telegram_id)

    return len([subscription.is_actual for subscription in client.client_subscriptions]) > 0


def is_client_phone(telegram_id: str) -> bool:  ## TODO !!!Может обозвать is_person_phone()?
    person = main_models.Person.objects.get(telegram_id=telegram_id)

    return True if person.phone else False


def update_client_phone(telegram_id: str,
                        phonenumber: str) -> None:

    main_models.Person.objects.filter(telegram_id=telegram_id).update(phone=phonenumber)


def create_request(telegram_id: str,
                   message: str):
    ### TODO что имеется ввиду?
    return


def get_tariffs() -> QuerySet:
    return main_models.Tariff.objects.all()
