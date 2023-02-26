from ast import Delete
from contextlib import suppress
from pydoc import visiblename
from textwrap import dedent
from functools import partial
from time import sleep
import re
import os
from uuid import uuid4

from django.core.management.base import BaseCommand
from environs import Env
from more_itertools import chunked
from phonenumber_field.validators import (
    validate_international_phonenumber,
    ValidationError
)
from redis import Redis
from telegram import (
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    LabeledPrice,
    Contact
)
from telegram.error import BadRequest
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    Filters,
    PreCheckoutQueryHandler
)

import main.management.commands.db_processing as db
import main.management.commands.messages as messages
import main.management.commands.buttons as buttons


START_INLINE = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(**buttons.I_AM_CLIENT),
            InlineKeyboardButton(**buttons.I_AM_CONTACTOR)
        ],
        [
            InlineKeyboardButton(**buttons.I_AM_MANAGER),
            InlineKeyboardButton(**buttons.I_AM_OWNER)
        ],
    ]
)


VISITOR_INLINE_KEYBOARD = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton(**buttons.NEW_CLIENT),
            InlineKeyboardButton(**buttons.NEW_CONTRACTOR)
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
        [InlineKeyboardButton(**buttons.NEW_CONTRACTOR)]
    ]
)

CONTRACTOR_INLINE_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton]
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

def delete_prev_inline(func, *args, **kwargs):
    def wrapper(*args, **kwargs):
        try:
            update, context = args[-2:]
        except ValueError:
            update, context = kwargs['update'], kwargs['context']
        if update.callback_query:
            with suppress(BadRequest):
                context.bot.edit_message_reply_markup(
                    chat_id=update.effective_chat.id,
                    message_id=update.callback_query.message.message_id,
                )
        return func(*args, **kwargs)
    return wrapper


def check_subscription(func, *args, **kwargs):
    def wrapper(*args, **kwargs):
        try:
            update, context = args[-2:]
        except ValueError:
            update, context = kwargs['update'], kwargs['context']
        if db.is_actual_subscription(telegram_id=update.effective_chat.id):
            return func(*args, **kwargs)
        else:
            return subscription_alert(update=update, context=context)
    return wrapper


def check_available_request(func, *args, **kwargs):
    def wrapper(*args, **kwargs):
        try:
            update, context = args[-2:]
        except ValueError:
            update, context = kwargs['update'], kwargs['context']
        if db.is_available_request(telegram_id=update.effective_chat.id):
            return func(*args, **kwargs)
        else:
            return available_requests_alert(update=update, context=context)
    return wrapper


def start(update: Update, context: CallbackContext) -> str:
    if not db.get_person(telegram_id=update.effective_chat.id):
        return hello_visitor(update=update, context=context)
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.CHECK_ROLE,
        reply_markup=START_INLINE
    )
    return 'VISITOR'

@delete_prev_inline
def check_access(update: Update, context: CallbackContext) -> str:
    _, claimed_role = update.callback_query.data.split(":::")
    
    if claimed_role == 'admin':
        if db.is_admin(telegram_id=update.effective_chat.id):
            return hello_admin(update=update, context=context)
        else:
            context.bot.send_message(
                update.effective_chat.id,
                text=messages.NOT_ADMIN,
                reply_markup=START_INLINE
            )
    elif claimed_role == 'manager':
        if db.is_manager(telegram_id=update.effective_chat.id):
            return hello_manager(update=update, context=context)
        else:
            context.bot.send_message(
                update.effective_chat.id,
                text=messages.NOT_MANAGER,
                reply_markup=START_INLINE
            )
    elif claimed_role == 'contractor':
        if db.is_contractor(telegram_id=update.effective_chat.id):
            return hello_contractor(update=update, context=context)
        else:
            context.bot.send_message(
                update.effective_chat.id,
                text=messages.NOT_CONTRACTOR,
                reply_markup=START_INLINE
            )
    elif claimed_role == 'client':
        return new_client(update=update, context=context)
    return 'VISITOR'
    





def subscription_alert(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        messages.SUBSCRIPTION_ALERT
    )
    sleep(2)
    return tell_about_subscription(update=update, context=context)


def available_requests_alert(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NO_AVAILABLE_REQUESTS,
        reply_markup=SUBSCRIPTION_KEYBOARD
    )
    return 'CLIENT'


def hello_visitor(update: Update, context: CallbackContext) -> str:
    context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=open('privacy_policy.pdf', 'rb'),
            caption=messages.HELLO_VISITOR,
            reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton(
                text=buttons.PHONENUMBER_REQUEST,
                request_contact=True
            )]],
            resize_keyboard=True
        )
    )
    return 'VISITOR_PHONENUMBER'


def enter_phone(update: Update, context: CallbackContext) -> str:
    if update.message.contact:
        phonenumber = update.message.contact.phone_number
        if phonenumber[0] != '+':
            phonenumber = f'+{phonenumber}'
    elif re.match(r'^\+?\d{7,15}$', update.message.text):
        phonenumber = update.message.text
        if phonenumber[0] != '+':
            phonenumber = f'+{phonenumber}'
        try:
            validate_international_phonenumber(phonenumber)
        except ValidationError:
            context.bot.send_message(
                update.effective_chat.id,
                messages.invalid_number(phonenumber=phonenumber),
            )
            return 'VISITOR_PHONENUMBER'
    else:
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.invalid_number(phonenumber=update.message.text)
        )
        return 'VISITOR_PHONENUMBER'
    
    username = update.effective_chat.first_name or update.effective_chat.username \
        or update.effective_chat.last_name
    db.create_person(telegram_id=update.effective_chat.id, username=username, phonenumber=phonenumber)
    context.bot.send_message(
            update.effective_chat.id,
            messages.REGISTRATION_COMPLETE,
            reply_markup=ReplyKeyboardRemove()
        )
    return new_visitor_role(update=update, context=context)

@delete_prev_inline
def new_visitor_role(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NEW_VISITOR_ROLE,
        reply_markup=START_INLINE
    )
    return 'VISITOR'


@delete_prev_inline
def new_client(update: Update, context: CallbackContext) -> str:
    db.create_client(telegram_id=update.effective_chat.id)
    return hello_client(update=update, context=context)


@delete_prev_inline
def hello_client(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.CLIENT_MAIN,
        reply_markup=CLIENT_INLINE_KEYBOARD
    )
    return 'CLIENT'

@delete_prev_inline
@check_subscription
@check_available_request
def new_request(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.DESCRIBE_REQUEST,
        reply_markup=CANCEL_INLINE
    )
    return 'CLIENT_NEW_REQUEST'


@delete_prev_inline
@check_subscription
@check_available_request
def client_request_description(update: Update, context: CallbackContext) -> str:
    if len(update.message.text) > 1000:
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.TOO_MUCH_REQUEST_SYMBOLS,
            reply_markup=CANCEL_INLINE
        )
        return 'CLIENT_NEW_REQUEST'

    db.create_order(
        telegram_id=update.effective_chat.id,
        description=update.message.text
    )

    context.bot.send_message(
        update.effective_chat.id,
        messages.SUCCESS_REQUEST
    )
    sleep(2)
    return hello_client(update=update, context=context)


@delete_prev_inline
def display_current_orders(update: Update, context: CallbackContext) -> str:
    orders = db.get_current_client_orders(telegram_id=update.effective_chat.id)
    orders_buttons = list()
    message = 'Ваши заказы:'
    for num, order in enumerate(orders, start=1):
        message += f'\n\nЗаказ {num}.\n{order["created_at"]}: {order["description"][:50]}...'
        orders_buttons.append(InlineKeyboardButton(
            text=f'{buttons.ORDER["text"]} {num}',
            callback_data=f'{buttons.ORDER["callback_data"]}:::{order["id"]}'
        ))
    orders_buttons = list(chunked(orders_buttons, 3))
    orders_buttons.append([InlineKeyboardButton(**buttons.BACK_TO_CLIENT_MAIN)])
    context.bot.send_message(
        update.effective_chat.id,
        text=message,
        reply_markup=InlineKeyboardMarkup(orders_buttons)
    )
    return 'CLIENT'


@delete_prev_inline
def display_order(update: Update, context: CallbackContext) -> str:
    _, order_id = update.callback_query.data.split(':::')
    order = db.get_order(telegram_id=update.effective_chat.id, order_id=order_id)
    order_buttons = [
        [InlineKeyboardButton(
            text=buttons.ORDER_COMMENT['text'],
            callback_data=f'{buttons.ORDER_COMMENT["callback_data"]}:::{order_id}'
        )]
    ]
    if db.can_see_contractor_contacts(telegram_id=update.effective_chat.id):
        order_buttons.append([
            InlineKeyboardButton(
                text=buttons.CONTRACTOR_CONTACTS['text'],
                callback_data=f'{buttons.CONTRACTOR_CONTACTS["callback_data"]}:::{order_id}'
            )
        ])
    order_buttons.append([
        InlineKeyboardButton(
            text=buttons.ORDER_COMPLAINT['text'],
            callback_data=f'{buttons.ORDER_COMPLAINT["callback_data"]}:::{order_id}'
        )
    ])
    order_buttons.append([InlineKeyboardButton(**buttons.BACK_TO_CLIENT_MAIN)])
    context.bot.send_message(
        update.effective_chat.id,
        text=order.display(),
        reply_markup=InlineKeyboardMarkup(order_buttons)
    )
    return 'CLIENT'


@delete_prev_inline
def add_order_comment(redis: Redis, update: Update, context: CallbackContext) -> str:
    _, order_id = update.callback_query.data.split(':::')
    redis.set(f'{update.effective_chat.id}_order_id', order_id)
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NEW_CLIENT_COMMENT,
        reply_markup=CANCEL_INLINE
    )
    return 'CLIENT_NEW_COMMENT'

@delete_prev_inline
def client_comment_description(redis: Redis, update: Update, context: CallbackContext) -> str:
    if len(update.message.text) > 1000:
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.TOO_MUCH_REQUEST_SYMBOLS,
            reply_markup=CANCEL_INLINE
        )
        return 'CLIENT_NEW_COMMENT'
    order_id = redis.get(f'{update.effective_chat.id}_order_id')
    db.create_comment_from_client(
        order_id=order_id,
        comment=update.message.text
    )
    context.bot.send_message(
        update.effective_chat.id,
        messages.SUCCESS_COMMENT
    )
    redis.delete(f'{update.effective_chat.id}_order_id')
    sleep(2)
    return hello_client(update=update, context=context)

@delete_prev_inline
def add_order_complaint(redis: Redis, update: Update, context: CallbackContext) -> str:
    _, order_id = update.callback_query.data.split(':::')
    redis.set(f'{update.effective_chat.id}_order_id', order_id)
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NEW_CLIENT_COMMENT,
        reply_markup=CANCEL_INLINE
    )
    return 'CLIENT_NEW_COMPLAINT'

@delete_prev_inline
def client_complaint_description(redis: Redis, update: Update, context: CallbackContext) -> str:
    if len(update.message.text) > 1000:
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.TOO_MUCH_REQUEST_SYMBOLS,
            reply_markup=CANCEL_INLINE
        )
        return 'CLIENT_NEW_COMPLAINT'
    order_id = redis.get(f'{update.effective_chat.id}_order_id')
    db.create_client_order_complaint(
        order_id=order_id,
        complaint=update.message.text
    )
    context.bot.send_message(
        update.effective_chat.id,
        messages.SUCCESS_COMPLAINT
    )
    redis.delete(f'{update.effective_chat.id}_order_id')
    sleep(2)
    return hello_client(update=update, context=context)

@delete_prev_inline
def send_contractor_contact(update: Update, context: CallbackContext) -> str:
    _, order_id = update.callback_query.data.split(':::')
    try:
        contractor_contact_meta = db.get_order_contractor_contact(order_id=order_id)
        context.bot.send_contact(
            chat_id=update.effective_chat.id,
            contact=Contact(**contractor_contact_meta),
        )
    except db.EntityNotFoundError as error:
        context.bot.send_message(
            update.effective_chat.id,
            text=error.message
        )
    sleep(2)
    return display_order(update=update, context=context)


@delete_prev_inline
def send_current_tariff(update: Update, context: CallbackContext) -> str:
    client_tariff_info = db.get_client_subscription_info(telegram_id=update.effective_chat.id)
    context.bot.send_message(
        update.effective_chat.id,
        text=client_tariff_info
    )
    return hello_client(update=update, context=context)


@delete_prev_inline
def new_contractor(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NEW_CONTRACTOR,
        reply_markup=CANCEL_INLINE
    )
    return 'NEW_CONTRACTOR'


@delete_prev_inline
def new_contractor_message(update: Update, context: CallbackContext) -> str:
    if len(update.message.text) >= 1000:
        context.bot.send_message(
            update.effective_chat.id,
            messages.TOO_MUCH_REQUEST_SYMBOLS
        )
        return 'NEW_CONTRACTOR'
    
    db.create_contractor(
        telegram_id=update.effective_chat.id,
        comment=update.message.text
    )
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NEW_CONTRACTOR_CREATED
    )
    return new_client(update=update, context=context)


def hello_contractor(update: Update, context: CallbackContext) -> str:
    #TODO
    context.bot.send_message(
        update.effective_chat.id,
        'Поздравляю, вы подрядчик. Но мне пофиг, раздел бота не дописан!',
        reply_markup=START_INLINE
    )
    return 'VISITOR'


def hello_admin(update: Update, context: CallbackContext) -> str:
    #TODO
    context.bot.send_message(
        update.effective_chat.id,
        'Поздравляю, вы админ. Но мне пофиг, раздел бота не дописан!',
        reply_markup=START_INLINE
    )
    return 'VISITOR'


def hello_manager(update: Update, context: CallbackContext) -> str:
    #TODO
    context.bot.send_message(
        update.effective_chat.id,
        'Поздравляю, вы менеджер. Но мне пофиг, раздел бота не дописан!',
        reply_markup=START_INLINE
    )
    return 'VISITOR'


def tell_about_subscription(update: Update, context: CallbackContext) -> str:
    tariffs = db.get_tariffs()
    message = "Давайте расскажу про наши тарифные планы:\n"
    subscription_buttons = list()
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
        subscription_buttons.append(
            [
                InlineKeyboardButton(
                    text=f'Оформить подписку "{tariff.title}"',
                    callback_data=f'activate_subscription:{tariff.id}'
                )
            ]
        )
    subscription_buttons.append([InlineKeyboardButton(**buttons.CANCEL)])
    context.bot.send_message(
        update.effective_chat.id,
        message,
        reply_markup=InlineKeyboardMarkup(subscription_buttons)
    )
    return 'SUBSCRIPTION'


def activate_subscription(redis: Redis, update: Update, context: CallbackContext) -> str:
    _, tariff_id = update.callback_query.data.split(":")
    tariff = db.get_tariff(tariff_id=tariff_id)
    payload=str(uuid4())
    redis.set(payload, tariff_id)
    redis.set(f'{payload}_user_id', update.effective_chat.id)
    context.bot.send_invoice(
        chat_id=update.effective_chat.id,
        title=tariff.title,
        description=tariff.payment_description(),
        payload=payload,
        provider_token=os.getenv('YOOKASSA_TOKEN'),
        currency='RUB',
        prices=[
            LabeledPrice(label='RUB', amount=(tariff.price * 100))
        ]
    )
    return 'SUBSCRIPTION'
    

def confirm_payment(redis: Redis, update: Update, context: CallbackContext) -> None:
    context.bot.answer_pre_checkout_query(
        pre_checkout_query_id=update.pre_checkout_query.id,
        ok=True
    )
    payload = update.pre_checkout_query.invoice_payload
    tariff_id = redis.get(payload)
    redis.delete(payload)
    telegram_id = redis.get(f'{payload}_user_id')
    redis.delete(f'{payload}_user_id')
    db.create_subscription(
        telegram_id=telegram_id,
        tariff_id=tariff_id,
        payment_id=payload
    )

@delete_prev_inline
def cancel_new_contractor(update: Update, context: CallbackContext) -> str:
    role = db.get_role(telegram_id=update.effective_chat.id)
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.OK,
        reply_markup=VISITOR_INLINE_KEYBOARD
    )
    if role:
        return role.upper()
    return 'VISITOR'


class Command(BaseCommand):
    help = "Start Telegram bot"

    def handle(self, *args, **kwargs):

        env = Env()
        env.read_env()

        updater = Updater(token=env.str('TELEGRAM_BOT_TOKEN'), use_context=True)
        redis = Redis(host='localhost', port=6379, db=0, decode_responses=True)

        
        updater.dispatcher.add_handler(
            ConversationHandler(
                entry_points = [
                    CommandHandler('start', start)
                ],
                states = {
                    'VISITOR': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(check_access, pattern=buttons.CHECK_ACCESS_CALLBACK),

                        CallbackQueryHandler(new_client, pattern=buttons.NEW_CLIENT['callback_data']),
                        CallbackQueryHandler(new_contractor, pattern=buttons.NEW_CONTRACTOR['callback_data']),
                    ],
                    'VISITOR_PHONENUMBER': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.all, callback=enter_phone),
                    ],
                    'SUBSCRIPTION': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(partial(activate_subscription, redis), pattern='activate_subscription'),
                        CallbackQueryHandler(new_visitor_role, pattern=buttons.CANCEL['callback_data']),
                        PreCheckoutQueryHandler(partial(confirm_payment, redis)),
                        MessageHandler(Filters.successful_payment, hello_client)
                    ],
                    'NEW_CONTRACTOR': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(new_client, pattern=buttons.CANCEL['callback_data']),
                        MessageHandler(Filters.text, new_contractor_message)
                    ],
                    'CLIENT': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(new_request, pattern=buttons.NEW_REQUEST['callback_data']),
                        CallbackQueryHandler(display_current_orders, pattern=buttons.CLIENT_CURRENT_ORDERS['callback_data']),
                        CallbackQueryHandler(display_order, pattern=buttons.ORDER['callback_data']),
                        CallbackQueryHandler(partial(add_order_comment, redis), pattern=buttons.ORDER_COMMENT['callback_data']),
                        CallbackQueryHandler(partial(add_order_complaint, redis), pattern=buttons.ORDER_COMPLAINT['callback_data']),
                        CallbackQueryHandler(send_contractor_contact, pattern=buttons.CONTRACTOR_CONTACTS['callback_data']),
                        CallbackQueryHandler(send_current_tariff, pattern=buttons.CLIENT_CURRENT_TARIFF['callback_data']),
                        CallbackQueryHandler(new_contractor, pattern=buttons.NEW_CONTRACTOR['callback_data']),
                        CallbackQueryHandler(hello_client, pattern=buttons.CANCEL['callback_data']),
                        CallbackQueryHandler(tell_about_subscription, pattern=buttons.CREATE_SUBSCRIPTION['callback_data']),
                        CallbackQueryHandler(hello_client, pattern=buttons.BACK_TO_CLIENT_MAIN['callback_data']),
                    ],
                    'CLIENT_NEW_REQUEST': [
                        MessageHandler(filters=Filters.text, callback=client_request_description),
                        CallbackQueryHandler(hello_client, pattern=buttons.CANCEL['callback_data']),

                    ],
                    'CLIENT_NEW_COMMENT': [
                        MessageHandler(filters=Filters.text, callback=partial(client_comment_description, redis)),
                        CallbackQueryHandler(hello_client, pattern=buttons.CANCEL['callback_data']),

                    ],
                    'CLIENT_NEW_COMPLAINT': [
                        MessageHandler(filters=Filters.text, callback=partial(client_complaint_description, redis)),
                        CallbackQueryHandler(hello_client, pattern=buttons.CANCEL['callback_data']),

                    ],
                    'CONTRACTOR': [

                    ],
                    'MANAGER': [

                    ],
                    'ADMIN': [

                    ]
                },
                fallbacks = [],

            )
        )
        
        updater.dispatcher.add_handler(PreCheckoutQueryHandler(partial(confirm_payment, redis)))

        updater.start_polling()
        updater.idle()