from main import models as main_models
from django.db.models import QuerySet

def get_role(telegram_id):
    return # 'client', 'contractor' or 'admin' 


def create_client(telegram_id: str,
                  username: str,
                  role: str = 'client') -> None:
    return

def get_client(telegram_id: str):
    return # объект клиента


def is_actual_subscription(telegram_id: str) -> bool:
    #TODO
    # check current subscription of client and return True or False
    return False

def is_client_phone(telegram_id: str) -> bool:
    #TODO
    # check if client.phone is not Null, return True or False
    return False 

def update_client_phone(telegram_id: str,
                        phonenumber: str) -> None:
    #TODO
    # person.phone = phonenumber
    # person.save()
    pass


def create_request(telegram_id: str,
                   message: str):
    return

def get_tariffs() -> QuerySet:
    return main_models.Tariff.objects.all()

