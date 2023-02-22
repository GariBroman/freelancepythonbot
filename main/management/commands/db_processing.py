from main import models as main_models

def get_role(telegram_id):
    return # 'client', 'contractor' or 'admin' 


def create_client(telegram_id: str,
                  username: str,
                  role: str = 'client') -> None:
    return

def get_client(telegram_id: str): #Добавить аннотацию модель клиента
    return # объект клиента


def is_client_phone(telegram_id: str) -> bool:
    # check if client.phone is not Null
    return False # return correct value

def update_client_phone(telegram_id: str,
                        phonenumber: str) -> None:
    # dont forget save object
    pass


def create_request(telegram_id: str,
                   message: str):
    return

def get_active_requests(telegram_id: str):
    pass

