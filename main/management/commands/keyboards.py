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

CLIENT_INLINE_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(**buttons.NEW_REQUEST)],
        [
            InlineKeyboardButton(**buttons.CLIENT_CURRENT_ORDERS),
            InlineKeyboardButton(**buttons.CLIENT_CURRENT_TARIFF)
        ],
        [InlineKeyboardButton(**buttons.CHANGE_ROLE)]
    ]
)

CONTRACTOR_INLINE_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(**buttons.CONTRACTOR_CURRENT_ORDERS)],
        [InlineKeyboardButton(**buttons.CONTRACTOR_AVAILABLE_ORDERS)],
        [InlineKeyboardButton(**buttons.CHANGE_ROLE)],

    ]
)

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
