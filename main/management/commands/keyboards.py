from django.db.models import QuerySet
from more_itertools import chunked
from telegram import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

import main.management.commands.buttons as buttons

from main import models as main_models


BACK_TO_CONTRACTOR_MAIN = InlineKeyboardMarkup(
    [[InlineKeyboardButton(**buttons.BACK_TO_CONTRACTOR_MAIN)]]
)

START_INLINE = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(**buttons.I_AM_CLIENT),
            InlineKeyboardButton(**buttons.I_AM_CONTACTOR)
        ]
    ]
)

BECOME_CONTRACTOR_INLINE = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(**buttons.NEW_CONTRACTOR),
            InlineKeyboardButton(**buttons.CHANGE_ROLE)
        ]

    ]
)

CLIENT_INLINE_KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton(**buttons.SELECT_CATEGORY)],
    [InlineKeyboardButton(**buttons.MY_CART)],
    [InlineKeyboardButton(**buttons.CLIENT_CURRENT_ORDERS)],
    [InlineKeyboardButton(**buttons.CHANGE_ROLE)]
])

CONTRACTOR_INLINE_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton(**buttons.CONTRACTOR_AVAILABLE_ORDERS)
    ],
    [InlineKeyboardButton(**buttons.MY_SERVICES)],
    [InlineKeyboardButton(**buttons.SWITCH_TO_CLIENT)]
])

SUBSCRIPTION_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(**buttons.CREATE_SUBSCRIPTION)],
        [InlineKeyboardButton(**buttons.BACK_TO_CLIENT_MAIN)]
    ]
)

CANCEL_INLINE = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(**buttons.CANCEL)]
    ]
)

PHONE_REQUEST_MARKUP = ReplyKeyboardMarkup(
    [[
        KeyboardButton(
            text=buttons.PHONENUMBER_REQUEST,
            request_contact=True
        )
    ]],
    resize_keyboard=True
)


def client_orders_inline(orders: QuerySet,
                         enumerate_start: int = 1) -> InlineKeyboardMarkup:
    orders_buttons = list()
    for num, order in enumerate(orders, enumerate_start):
        orders_buttons.append(InlineKeyboardButton(
            text=f'{buttons.ORDER["text"]} {num}',
            callback_data=f'{buttons.ORDER["callback_data"]}:::{order.id}'
        ))
    orders_buttons = list(chunked(orders_buttons, 3))
    orders_buttons.append([InlineKeyboardButton(**buttons.BACK_TO_CLIENT_MAIN)])
    return InlineKeyboardMarkup(orders_buttons)


def client_order_inline(order: main_models.Order,
                        can_see_contractor_contact: bool = False) -> InlineKeyboardMarkup:
    order_buttons = [
        [InlineKeyboardButton(
            text=buttons.ORDER_COMMENT['text'],
            callback_data=f'{buttons.ORDER_COMMENT["callback_data"]}:::{order.id}'
        )]
    ]
    if can_see_contractor_contact:
        order_buttons.append([
            InlineKeyboardButton(
                text=buttons.CONTRACTOR_CONTACTS['text'],
                callback_data=f'{buttons.CONTRACTOR_CONTACTS["callback_data"]}:::{order.id}'
            )
        ])
    order_buttons += [
        [
            InlineKeyboardButton(
                text=buttons.ORDER_COMPLAINT['text'],
                callback_data=f'{buttons.ORDER_COMPLAINT["callback_data"]}:::{order.id}'
            )
        ],
        [InlineKeyboardButton(**buttons.BACK_TO_CLIENT_MAIN)]
    ]
    return InlineKeyboardMarkup(order_buttons)


def contractor_orders_inline(orders: QuerySet,
                             are_current_orders: bool = False,
                             are_available_orders: bool = False,
                             enumerate_start: int = 1):
    orders_buttons = list()
    if are_current_orders:
        for num, order in enumerate(orders, enumerate_start):
            orders_buttons.append(InlineKeyboardButton(
                text=f'{buttons.CURRENT_ORDER["text"]} {num}',
                callback_data=f'{buttons.CURRENT_ORDER["callback_data"]}:::{order.id}'
            ))
    elif are_available_orders:
        for num, order in enumerate(orders, enumerate_start):
            orders_buttons.append(InlineKeyboardButton(
                text=f'{buttons.AVAILABLE_ORDER["text"]} {num}',
                callback_data=f'{buttons.AVAILABLE_ORDER["callback_data"]}:::{order.id}'
            ))
    orders_buttons = list(chunked(orders_buttons, 3))
    orders_buttons.append([InlineKeyboardButton(**buttons.BACK_TO_CONTRACTOR_MAIN)])
    return InlineKeyboardMarkup(orders_buttons)


def contractor_order_inline(order: main_models.Order,
                            is_current: bool = False,
                            is_available: bool = False) -> InlineKeyboardMarkup:
    if is_current:
        order_buttons = [
            [InlineKeyboardButton(
                text=buttons.FINISH_ORDER['text'],
                callback_data=f'{buttons.FINISH_ORDER["callback_data"]}:::{order.id}'
            )],
            [InlineKeyboardButton(
                text=buttons.CONTRACTOR_SET_ESTIMATE_DATETIME['text'],
                callback_data=f'{buttons.CONTRACTOR_SET_ESTIMATE_DATETIME["callback_data"]}:::{order.id}'
            )]
        ]
    elif is_available:
        order_buttons = [
            [InlineKeyboardButton(
                text=buttons.TAKE_ORDER['text'],
                callback_data=f'{buttons.TAKE_ORDER["callback_data"]}:::{order.id}'
            )]
        ]
    order_buttons.append([InlineKeyboardButton(**buttons.BACK_TO_CONTRACTOR_MAIN)])
    return InlineKeyboardMarkup(order_buttons)


def subscriptions_inline(tariffs: QuerySet) -> InlineKeyboardMarkup:
    subscription_buttons = [
        [
            InlineKeyboardButton(
                text=f'Оформить подписку "{tariff.title}"',
                callback_data=f'activate_subscription:{tariff.id}'
            )
        ]
        for tariff in tariffs
    ]
    subscription_buttons.append([InlineKeyboardButton(**buttons.CANCEL)])
    return InlineKeyboardMarkup(subscription_buttons)


def get_categories_keyboard():
    """Клавиатура с категориями услуг"""
    from main.management.commands.db_processing import get_service_categories
    
    categories = get_service_categories()
    keyboard = []
    
    # Добавляем кнопки категорий по 2 в ряд
    for chunk in chunked(categories, 2):
        row = []
        for category in chunk:
            row.append(InlineKeyboardButton(
                category.name,
                callback_data=buttons.CATEGORY_CALLBACK.format(category.id)
            ))
        keyboard.append(row)
    
    # Добавляем кнопку отмены
    keyboard.append([InlineKeyboardButton(**buttons.CANCEL)])
    
    return InlineKeyboardMarkup(keyboard)


def get_services_keyboard(category_id):
    """Клавиатура с услугами в категории"""
    from main.management.commands.db_processing import get_services_by_category
    
    services = get_services_by_category(category_id)
    keyboard = []
    
    # Добавляем кнопки услуг по 1 в ряд
    for service in services:
        keyboard.append([
            InlineKeyboardButton(
                f"{service.title} - {service.price} руб.",
                callback_data=buttons.SERVICE_CALLBACK.format(service.id)
            )
        ])
    
    # Добавляем кнопки навигации
    keyboard.append([
        InlineKeyboardButton(**buttons.BACK_TO_CLIENT_MAIN),
        InlineKeyboardButton(**buttons.MY_CART)
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_service_details_keyboard(service_id):
    """Клавиатура для детальной информации об услуге"""
    keyboard = [
        [InlineKeyboardButton(
            "Добавить в корзину",
            callback_data=buttons.ADD_TO_CART_CALLBACK.format(service_id)
        )],
        [
            InlineKeyboardButton(**buttons.BACK_TO_CLIENT_MAIN),
            InlineKeyboardButton(**buttons.MY_CART)
        ]
    ]
    
    return InlineKeyboardMarkup(keyboard)


def get_cart_keyboard(client_id):
    """Клавиатура для корзины услуг"""
    from main.management.commands.db_processing import get_client_service_set
    
    service_set = get_client_service_set(client_id)
    keyboard = []
    
    if service_set and service_set.services.exists():
        # Добавляем кнопки для удаления услуг из корзины
        for service in service_set.services.all():
            keyboard.append([
                InlineKeyboardButton(
                    f"❌ {service.title} - {service.price} руб.",
                    callback_data=buttons.REMOVE_FROM_CART_CALLBACK.format(service.id)
                )
            ])
        
        # Добавляем кнопки действий
        keyboard.append([
            InlineKeyboardButton(**buttons.CLEAR_CART),
            InlineKeyboardButton(**buttons.CHECKOUT)
        ])
    
    # Добавляем кнопку возврата
    keyboard.append([InlineKeyboardButton(**buttons.BACK_TO_CLIENT_MAIN)])
    
    return InlineKeyboardMarkup(keyboard)


def get_contractor_services_keyboard(contractor_id):
    """Клавиатура с услугами исполнителя"""
    from main.management.commands.db_processing import get_contractor_services
    
    services = get_contractor_services(contractor_id)
    keyboard = []
    
    # Добавляем кнопки услуг
    for service in services:
        keyboard.append([
            InlineKeyboardButton(
                f"{service.title} - {service.price} руб.",
                callback_data=buttons.EDIT_SERVICE_CALLBACK.format(service.id)
            )
        ])
    
    # Добавляем кнопки действий
    keyboard.append([
        InlineKeyboardButton(**buttons.ADD_SERVICE),
        InlineKeyboardButton(**buttons.BACK_TO_CONTRACTOR_MAIN)
    ])
    
    return InlineKeyboardMarkup(keyboard)


def get_service_edit_keyboard(service_id):
    """Клавиатура для редактирования услуги"""
    keyboard = [
        [InlineKeyboardButton(
            "✏️ Изменить название",
            callback_data=f"edit_service_title:{service_id}"
        )],
        [InlineKeyboardButton(
            "✏️ Изменить описание",
            callback_data=f"edit_service_description:{service_id}"
        )],
        [InlineKeyboardButton(
            "✏️ Изменить цену",
            callback_data=f"edit_service_price:{service_id}"
        )],
        [InlineKeyboardButton(
            "✏️ Изменить категорию",
            callback_data=f"edit_service_category:{service_id}"
        )],
        [InlineKeyboardButton(
            "✏️ Изменить фото",
            callback_data=f"edit_service_photo:{service_id}"
        )],
        [InlineKeyboardButton(
            "🗑️ Удалить услугу",
            callback_data=buttons.DELETE_SERVICE_CALLBACK.format(service_id)
        )],
        [InlineKeyboardButton(
            "⬅️ Назад к моим услугам",
            callback_data=buttons.MY_SERVICES['callback_data']
        )]
    ]
    
    return InlineKeyboardMarkup(keyboard)
