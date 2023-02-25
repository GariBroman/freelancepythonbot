from pydoc import visiblename
from textwrap import dedent
from functools import partial
from time import sleep
import re
import os
from uuid import uuid4

from django.core.management.base import BaseCommand
from environs import Env
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
    LabeledPrice
)
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

VISITOR_INLINE_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(**buttons.NEW_CLIENT)],
        [InlineKeyboardButton(**buttons.NEW_CONTRACTOR)]

    ]
)

CLIENT_INLINE_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(**buttons.NEW_REQUEST)],
        [InlineKeyboardButton(**buttons.NEW_CONTRACTOR)]
    ]
)

SUBSCRIPTION_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(**buttons.CREATE_SUBSCRIPTION)]
    ]
)
NEW_CONTRUCTOR_INLINE_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(**buttons.FILL_CONTRACTOR_FORM)],
        [InlineKeyboardButton(**buttons.CONTRACTOR_SALARY)],
        [InlineKeyboardButton(**buttons.CANCEL_NEW_CONTRACTOR)]
    ]
)

CANCEL_INLINE = InlineKeyboardMarkup(
    [[
        InlineKeyboardButton(**buttons.CANCEL)
    ]]
)


def check_access(update: Update, context: CallbackContext) -> str:
    role = db.get_role(telegram_id=update.effective_chat.id)
    if role == 'admin':
        return hello_admin(update=update, context=context)
    elif role == 'manager':
        return hello_manager(update=update, context=context)
    elif role == 'contractor':
        return hello_contractor(update=update, context=context)
    elif role == 'client':
        return hello_client(update=update, context=context)
    return hello_visitor(update=update, context=context)


def delete_prev_inline(func, *args, **kwargs):
    def wrapper(*args, **kwargs):
        update, context = args[-2:]
        context.bot.edit_message_reply_markup(
            chat_id=update.effective_chat.id,
            message_id=update.callback_query.message.message_id,
        )
        return func(*args, **kwargs)
    return wrapper


def check_subscription(func, *args, **kwargs):
    def wrapper(*args, **kwargs):
        update, context = args[-2:]
        if db.is_actual_subscription(telegram_id=update.effective_chat.id):
            return func(*args, **kwargs)
        else:
            return subscription_alert(update=update, context=context)
    return wrapper


def subscription_alert(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        messages.SUBSCRIPTION_ALERT
    )
    sleep(2)
    return tell_about_subscription(update=update, context=context)


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


def new_visitor_role(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NEW_VISITOR_ROLE,
        reply_markup=VISITOR_INLINE_KEYBOARD
    )
    return 'VISITOR'


@delete_prev_inline
def new_client(update: Update, context: CallbackContext) -> str:
    db.create_client(telegram_id=update.effective_chat.id)
    return subscription_alert(update=update, context=context)



@check_subscription
def hello_client(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text="Добро пожаловать!",
        reply_markup=CLIENT_INLINE_KEYBOARD
    )
    return 'CLIENT'


def hello_contractor(update: Update, context: CallbackContext) -> str:
    #TODO
    return 'CONTRACTOR'


def hello_admin(update: Update, context: CallbackContext) -> str:
    #TODO
    return 'CONTRACTOR'


def hello_manager(update: Update, context: CallbackContext) -> str:
    #TODO
    return 'CONTRACTOR'


def tell_about_subscription(update: Update, context: CallbackContext) -> str:
    tariffs = db.get_tariffs()
    message = "Давайте расскажу про наши тарифные планы:\n"
    subscription_buttons = list()
    for tariff in tariffs:
        message += dedent(
                f"""
                {tariff.title}:
                {tariff.orders_limit} заявок в месяц.
                Время ответа на заявку: {tariff.answer_delay}
                Время ответа на заявку: tariff.display_answer_delay() TODO
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
            LabeledPrice(label='RUB', amount=tariff.int_price())
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
def new_contractor(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NEW_CONTRACTOR,
        reply_markup=NEW_CONTRUCTOR_INLINE_KEYBOARD
    )
    return 'VISITOR'


@delete_prev_inline
def contractor_salary(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NEW_CONTRACTOR_SALARY,
        reply_markup=NEW_CONTRUCTOR_INLINE_KEYBOARD
    )
    return 'VISITOR'


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





@delete_prev_inline
@check_subscription
def new_request(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.DESCRIBE_REQUEST,
        reply_markup=CANCEL_INLINE
    )
    return 'CLIENT'


def client_message(redis: Redis, update: Update, context: CallbackContext) -> str:
    if len(update.message.text) > 1000:
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.TOO_MUCH_REQUEST_SYMBOLS,
            reply_markup=CANCEL_INLINE
        )
        return 'CLIENT'

    if redis.get(f'{update.effective_chat.id}_message'):
        return enter_phone(redis=redis, update=update, context=context)

    redis.set(f'{update.effective_chat.id}_message', update.message.text)
    
    if not db.is_client_phone(telegram_id=update.effective_chat.id): 
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.ASK_PHONENUMBER,
            reply_markup=ReplyKeyboardMarkup(
                [
                    [KeyboardButton(text='Поделиться номером', request_contact=True)]
                ],
                resize_keyboard=True,
            )
        )
        context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=open('privacy_policy.pdf', 'rb'),
            caption='Отправляя ваши персональные данные вы соглашаетесь с политикой конфиденциальности.',
            reply_markup=CANCEL_INLINE
        )
        return 'CLIENT'
    return finish_request(redis=redis, update=update, context=context)





@check_subscription
def finish_request(redis: Redis, update: Update, context: CallbackContext) -> str:
    message = redis.get(f'{update.effective_chat.id}_message')
    db.create_request(telegram_id=update.effective_chat.id, message=message)
    redis.delete(f'{update.effective_chat.id}_message')
    context.bot.send_message(
        update.effective_chat.id,
        messages.SUCCESS_REQUEST,
        reply_markup=CLIENT_INLINE_KEYBOARD
    )
    return 'CLIENT'


@delete_prev_inline
def cancel_new_request(redis: Redis, update: Update, context: CallbackContext) -> str:
    redis.delete(f'{update.effective_chat.id}_message')
    context.bot.send_message(
        update.effective_chat.id,
        text='Как скажете',
        reply_markup=ReplyKeyboardRemove()
    )
    context.bot.send_message(
        update.effective_chat.id,
        text='Возвращаемся на главную',
        reply_markup=CLIENT_INLINE_KEYBOARD
    )
    return 'CLIENT'



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
                    CommandHandler('start', check_access)
                ],
                states = {
                    'VISITOR': [
                        CallbackQueryHandler(new_client, pattern=buttons.NEW_CLIENT['callback_data']),
                        CallbackQueryHandler(new_contractor, pattern=buttons.NEW_CONTRACTOR['callback_data']),
                        CallbackQueryHandler(cancel_new_contractor, pattern=buttons.CANCEL_NEW_CONTRACTOR['callback_data']),
                        CallbackQueryHandler(contractor_salary, pattern=buttons.CONTRACTOR_SALARY['callback_data'])
                    ],
                    'VISITOR_PHONENUMBER': [
                        MessageHandler(filters=Filters.all, callback=enter_phone),
                    ],
                    'NEW_CLIENT': [

                    ],
                    'SUBSCRIPTION': [
                        CallbackQueryHandler(partial(activate_subscription, redis), pattern='activate_subscription'),
                        CallbackQueryHandler(partial(cancel_new_request, redis), pattern=buttons.CANCEL['callback_data']),
                        PreCheckoutQueryHandler(partial(confirm_payment, redis)),
                        MessageHandler(Filters.successful_payment, hello_client)
                    ],
                    'NEW_CONTRACTOR_FORM': [

                    ],
                    'CLIENT': [
                        
                        CallbackQueryHandler(new_request, pattern=buttons.NEW_REQUEST['callback_data']),
                        CallbackQueryHandler(partial(cancel_new_request, redis), pattern=buttons.CANCEL['callback_data']),
                    ],
                    'CONTRACTOR': [

                    ],
                    'ADMIN': [

                    ]
                },
                fallbacks = [

                ]
            )
        )
        
        updater.dispatcher.add_handler(PreCheckoutQueryHandler(partial(confirm_payment, redis)))

        updater.start_polling()
        updater.idle()