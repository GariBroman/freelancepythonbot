from pydoc import visiblename
from textwrap import dedent
from functools import partial

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
    InlineKeyboardButton
)
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler,
    Filters
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

CUSTOMER_INLINE_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(**buttons.NEW_REQUEST)],
        [InlineKeyboardButton(**buttons.NEW_CONTRACTOR)]
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


def delete_prev_inline(func, *args, **kwargs):
    def wrapper(*args, **kwargs):
        update, context = args[-2:]
        context.bot.edit_message_reply_markup(
            chat_id=update.effective_chat.id,
            message_id=update.callback_query.message.message_id,
        )
        return func(*args, **kwargs)
    return wrapper


def check_access(update: Update, context: CallbackContext) -> str:
    role = db.get_role(telegram_id=update.effective_chat.id)
    if role == 'admin':
        # send smth to admin

        return 'ADMIN'
    elif role == 'contractor':
        # send smth to contractor

        return 'CONTRACTOR'
    elif role == 'client':
        context.bot.send_message(
            update.effective_chat.id,
            text=dedent(
                """
                Добро пожаловать!
                """
            ),
            reply_markup=CUSTOMER_INLINE_KEYBOARD
        )
        return 'CLIENT'
    
    # make smth with new user
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.HELLO_VISITOR,
        reply_markup=VISITOR_INLINE_KEYBOARD
    )
    return 'VISITOR'


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
def new_client(update: Update, context: CallbackContext) -> str:
    username = update.effective_chat.first_name or update.effective_chat.username or update.effective_chat.last_name
    db.create_client(telegram_id=update.effective_chat.id, username=username)
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.WELCOME,
        reply_markup=CUSTOMER_INLINE_KEYBOARD
    )
    return 'CLIENT'


@delete_prev_inline
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


def enter_phone(redis: Redis, update: Update, context: CallbackContext) -> str:
    message = redis.get(f'{update.effective_chat.id}_message')
    if not message:
        context.bot.send_message(
            update.effective_chat.id,
            messages.PHONE_INSTEAD_REQUEST,
        )
        return 'CLIENT'
    if not update.message.contact:
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
            return 'CLIENT'
    else:
        phonenumber = update.message.contact.phone_number
        if phonenumber[0] != '+':
            phonenumber = f'+{phonenumber}'
    db.update_client_phone(telegram_id=update.effective_chat.id, phonenumber=phonenumber)
    context.bot.send_message(
            update.effective_chat.id,
            messages.PHONE_SAVED,
            reply_markup=ReplyKeyboardRemove()
        )
    return finish_request(redis=redis, update=update, context=context)


def finish_request(redis: Redis, update: Update, context: CallbackContext) -> str:
    message = redis.get(f'{update.effective_chat.id}_message')
    db.create_request(telegram_id=update.effective_chat.id, message=message)
    redis.delete(f'{update.effective_chat.id}_message')
    context.bot.send_message(
        update.effective_chat.id,
        messages.SUCCESS_REQUEST,
        reply_markup=CUSTOMER_INLINE_KEYBOARD
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
        reply_markup=CUSTOMER_INLINE_KEYBOARD
    )
    return 'CLIENT'


@delete_prev_inline
def show_requests(update: Update, context: CallbackContext) -> str:
    pass


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
                    'NEW_CONTRACTOR_FORM': [

                    ],
                    'CLIENT': [
                        MessageHandler(filters=Filters.regex(r'^\+?\d{7,15}$'), callback=partial(enter_phone, redis)),
                        MessageHandler(filters=Filters.contact, callback=partial(enter_phone, redis)),
                        MessageHandler(filters=Filters.text, callback=partial(client_message, redis)),
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
        


        updater.start_polling()
        updater.idle()