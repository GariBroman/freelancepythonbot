from textwrap import dedent

from django.db.models import QuerySet

import main.management.commands.buttons as buttons

from main import models as main_models

APPROVE_ORDER_CONTRACTOR = 'Заказ ваш!'

CHECK_ROLE = 'Укажите кто вы.'

CLIENT_MAIN = """
Вы на главной странице заказчика

Выберите категорию услуг, чтобы найти подходящего фрилансера, или перейдите в корзину, чтобы оформить заказ.
"""

CONTRACTOR_MAIN = """
Вы на главной странице фрилансера

Вы можете добавить новую карточку услуги, управлять существующими услугами или просматривать заказы.
"""

CONTRACTOR_NOT_FOUND = 'Исполнитель на ваш заказ еще не назначен. 🙏'

DESCRIBE_REQUEST = dedent(
    """
    Опишите тезисно вашу проблему.

    ❗️ У вас есть на это 1000 символов с учетом пробелов и спец. символов.
    """
)

HELLO_VISITOR = dedent(
    f"""
    Здравствуйте!
    Для регистрации введите 📱 номер телефона или нажмите кнопку ⬇️ "{buttons.PHONENUMBER_REQUEST}".

    ❗️ Отправляя ваши персональные данные вы соглашаетесь с политикой конфиденциальности.
    """
)

NEW_CLIENT_COMMENT = dedent(
    """
    Напишите ваш комментарий к заказу и мы сразу уведомим администратора и исполнителя о вашем пожелании.

    ❗️ Максимально 1000 символов.
    """
)

NEW_CONTRACTOR = dedent(
    """
    Для того, чтобы стать исполнителем, вам необходимо написать на чем вы специализируетесь.
    (Уложитесь пожалуста в 1000 символов)...

    С вами свяжется наш менеджер, проведет собеседование и расскажет детали.
    """
)

NEW_CONTRACTOR_CREATED = dedent(
    """
    Ваша заявка передана администратору.

    Ожидайте, с вами свяжутся в течение суток
    """
)

NO_ACTIVE_ORDERS = 'У вас нет активных заказов'

NO_ACTIVE_SUBSCRIPTIONS = 'У вас нет активных подписок'

NO_AVAILABLE_ORDERS = 'У вас нет доступных заказов'

NO_AVAILABLE_REQUESTS = dedent(
    """
    ❌ Похоже что вы достилги лимита заявок по вашей подписке.

    Нужно больше заявок, можете приобрести дополнитеную подписку.
    """
)

NOT_CONTRACTOR = dedent(
    """
    ❌ Вы не числитесь как активный подрядчик.
    """
)

OK = 'Как скажете'

ORDER_CLOSED = 'Заказ закрыт'

REGISTRATION_COMPLETE = 'Вы успешно зарегистрировались'

SET_ESTIMATE_DATETIME = 'Введите дату и время в формате ГГГГ:ММ:ДД:ЧЧ:ММ'

SUBSCRIPTION_ALERT = "❗️ Для использования сервиса вам необходимо приобрести подписку"

SUCCESS_COMMENT = '✅ Ваш комментарий отправлен'

SUCCESS_COMPLAINT = '✅ Ваша претензия отправлена'

SUCCESS_REQUEST = dedent(
    '''
    ✅ Заявка отправлена!
    Ожидайте звонка менеджера!
    '''
)

TOO_MUCH_REQUEST_SYMBOLS = dedent(
    """
    ‼️ Превышен лимит символов.

    ❗️ У вас есть на это 1000 символов с учетом пробелов и спец. символов.
    """
)

WELCOME = "Добро пожаловать! 🤗"

# Сообщения для работы с категориями и услугами
WELCOME_MESSAGE = """
👋 Добро пожаловать в бота!

Здесь вы можете выбрать режим работы:
- Заказчик: поиск и заказ услуг
- Фрилансер: предоставление услуг

Пожалуйста, подпишитесь на наш канал для получения новостей и обновлений:
@https://t.me/visitka_chat
"""

SELECT_CATEGORY_MESSAGE = """
Выберите категорию услуг:
"""

SERVICE_DETAILS_TEMPLATE = """
<b>{title}</b>

<b>Описание:</b> {description}

<b>Цена:</b> {price} руб.

<b>Исполнитель:</b> {contractor_name}
"""

CART_EMPTY_MESSAGE = """
Ваша корзина пуста.

Выберите категорию услуг, чтобы добавить услуги в корзину.
"""

CART_TEMPLATE = """
<b>Ваша корзина:</b>

{services}

<b>Итого:</b> {total_price} руб.{discount}
"""

CONTRACTOR_SERVICES_EMPTY = """
У вас пока нет добавленных услуг.

Нажмите "Добавить услугу", чтобы создать новую карточку услуги.
"""

CONTRACTOR_SERVICES_MESSAGE = """
<b>Ваши услуги:</b>

Выберите услугу для редактирования или добавьте новую.
"""

ADD_SERVICE_TITLE_MESSAGE = """
Введите название услуги:
"""

ADD_SERVICE_DESCRIPTION_MESSAGE = """
Введите описание услуги:
"""

ADD_SERVICE_PRICE_MESSAGE = """
Введите стоимость услуги (только число):
"""

ADD_SERVICE_PHOTO_MESSAGE = """
Отправьте фото для услуги или нажмите "Пропустить":
"""

SERVICE_ADDED_MESSAGE = """
✅ Услуга успешно добавлена!
"""

SERVICE_UPDATED_MESSAGE = """
✅ Услуга успешно обновлена!
"""

SERVICE_DELETED_MESSAGE = """
✅ Услуга успешно удалена!
"""

ADDED_TO_CART_MESSAGE = """
✅ Услуга добавлена в корзину!
"""

REMOVED_FROM_CART_MESSAGE = """
✅ Услуга удалена из корзины!
"""

CART_CLEARED_MESSAGE = """
✅ Корзина очищена!
"""

CHECKOUT_MESSAGE = """
Для оформления заказа, пожалуйста, перейдите по ссылке ниже для оплаты на сайте консалтинговой фирмы.
"""

CONTRACTOR_WELCOME_MESSAGE = """
Добро пожаловать в режим фрилансера!

Здесь вы можете управлять своими услугами, добавлять новые карточки услуг и получать заказы.
"""

CLIENT_WELCOME_MESSAGE = """
Добро пожаловать в режим заказчика!

Здесь вы можете выбирать и заказывать услуги фрилансеров.
Для начала выберите категорию услуг, затем выберите подходящего фрилансера и добавьте его услугу в корзину.
После формирования заказа вы будете перенаправлены на сайт консалтинговой фирмы для оплаты.
"""

def invalid_number(phonenumber: str) -> str:
    return dedent(
        f'''
        Похожу что вы с ошибкой отправили номер телефона.
        Не могу распознать номер "{phonenumber}".
        Попробуйте еще раз или просто воспользуйтесь кнопкой.

        ВНИМАНИЕ! Регистрация является обязательным условием использования сервиса.
        '''
    )


def tell_about_subscription(tariffs: QuerySet) -> str:
    message = "Давайте расскажу про наши тарифные планы:\n"
    for tariff in tariffs:
        message += dedent(
                f"""
                {tariff.title}:
                {tariff.orders_limit} заявок в месяц.

                Время ответа на заявку: {tariff.display_answer_delay()}
                """
        )
        if tariff.personal_contractor_available:
            message += dedent(
                """
                Возможность закрепить за собой подрядчика.
                """
            )
        if tariff.contractor_contacts_availability:
            message += dedent(
                """
                Возможность увидеть контакты подрядчика.
                """
            )
    return message


def new_order_notification(order: str) -> str:
    return dedent(
        f"""
        NEW ORDER

        {order}
        """
    )


def new_subscription_notification(subscription: main_models.ClientSubscription) -> str:
    return dedent(
        f"""
        NEW SUBSCRIPTION

        {subscription}
        """
    )


def new_client_comment_notification(order: main_models.Order, comment: main_models.OrderComments) -> str:
    return dedent(
        f"""
        NEW COMMENT
        order: {order}

        comment: {comment}
        """
    )


def new_client_complaint_notification(order: main_models.Order, complaint: main_models.Complaint) -> str:
    return dedent(
        f"""
        NEW COMPLAINT
        order: {order}

        comment: {complaint}
        """
    )


def new_contractor_notification(contractor: main_models.Contractor, message: str) -> str:
    return dedent(
        f"""
        NEW CONTRACTOR
        contractor: {contractor}

        request: {message}
        """
    )


def contractor_took_order_notification(order: main_models.Order) -> str:
    return dedent(
        f"""
        CONTRACTOR TAKE ORDER
        contractor: {order.contractor}

        order_id: {order}
        """
    )


def contractor_finished_order_notification(order: main_models.Order) -> str:
    return dedent(
        f"""
        CONTRACTOR closed ORDER
        contractor: {order.contractor}

        request: {order}
        """
    )


def contractor_set_estimate_datetime_notifiction(order: main_models.Order) -> str:
    return dedent(
        f"""
        CONTRACTOR SET ORDER estimate datetime
        {order.estimated_time.strftime("%d.%m.%Y %H:%M")}

        order: {order}
        """
    )


def display_orders(orders: QuerySet,
                   are_current: bool = False,
                   are_available: bool = False,
                   enumerate_start: int = 1) -> str:
    message = 'Ваши текущие заказы:' if are_current == True else \
        'Доступные вам заказы:' if are_available == True else \
        'Ваши заказы:'
    for num, order in enumerate(orders, start=enumerate_start):
        message += dedent(
            f'''
            Заказ {num}.
            {order.display()}
            '''
        )
    return message
