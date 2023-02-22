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


VISITOR_INLINE_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(text='Мне нужна техподдержка', callback_data='new_customer')],
        [InlineKeyboardButton(text='Я сам техподдержка', callback_data='new_contractor')]

    ]
)
CUSTOMER_INLINE_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(text='Отправить заявку', callback_data='new_request')],
        [InlineKeyboardButton(text='Хочу стать исполнителем', callback_data='new_contractor')]
    ]
)


NEW_CONTRUCTOR_INLINE_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton(text='Заполнить анкету', callback_data='fill_contractor_form')],
        [InlineKeyboardButton(text='Сколько я буду зарабатывать', callback_data='contractor_salary')],
        [InlineKeyboardButton(text='Я передумал', callback_data='cancel_new_contractor')]
    ]
)

CANCEL_INLINE = InlineKeyboardMarkup(
    [[
        InlineKeyboardButton(text="Я передумал", callback_data='cancel_new_request')
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
        text=dedent(
            """
            Здравствуйте!
            Я первая линия поддержки пользователей.
            """
        ),
        reply_markup=VISITOR_INLINE_KEYBOARD
    )
    return 'VISITOR'




@delete_prev_inline
def new_contractor(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=dedent(
            """
            Для того, чтобы стать исполнителем, вам необходимо заполнить анкету.
            С вами свяжется наш менеджер, проведет собеседование и расскажет детали.
            """
        ),
        reply_markup=NEW_CONTRUCTOR_INLINE_KEYBOARD
    )
    return 'VISITOR'


@delete_prev_inline
def contractor_salary(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text='Вы будете зарабатывать МНОГО ДЕНЕГ!!! 💰💰💰',
        reply_markup=NEW_CONTRUCTOR_INLINE_KEYBOARD
    )
    return 'VISITOR'


@delete_prev_inline
def cancel_new_contractor(update: Update, context: CallbackContext) -> str:
    role = db.get_role(telegram_id=update.effective_chat.id)
    context.bot.send_message(
        update.effective_chat.id,
        text='Как скажете',
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
        text=dedent(
            """
            Добро пожаловать!
            """
        ),
        reply_markup=CUSTOMER_INLINE_KEYBOARD
    )
    return 'CLIENT'


@delete_prev_inline
def new_request(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=dedent(
            """
            Опишите тезисно вашу проблему.

            ! У вас есть на это 1000 символов с учетом пробелов и спец. символов.
            """
        ),
        reply_markup=CANCEL_INLINE
    )
    return 'CLIENT'


def client_message(redis: Redis, update: Update, context: CallbackContext) -> str:
    if len(update.message.text) > 1000:
        context.bot.send_message(
            update.effective_chat.id,
            text=dedent(
                """
                Превышен лимит символов.

                ! У вас есть на это 1000 символов с учетом пробелов и спец. символов.
                """
            ),
            reply_markup=CANCEL_INLINE
        )
        return 'CLIENT'

    if redis.get(f'{update.effective_chat.id}_message'):
        return enter_phone(redis=redis, update=update, context=context)

    redis.set(f'{update.effective_chat.id}_message', update.message.text)
    
    if not db.is_client_phone(telegram_id=update.effective_chat.id): 
        context.bot.send_message(
            update.effective_chat.id,
            text=dedent(
                """
                Осталась небольшая формальность.

                Нам нужен номер вашего телефона, чтобы мы смогли связаться с вами.

                Можете ввести его в международном формате или просто нажать кнопку "Поделиться номером".

                """
            ),
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
            dedent(
                f'''
                Мне показалось или вы отправили номер телефона вместо сообщения?

                Не торопитесь, опишите сначала проблему.
                '''
            ),
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
                dedent(
                    f'''
                    Похожу что вы с ошибкой отправили номер телефона.
                    Не могу распознать номер "{phonenumber}".
                    Попробуйте еще раз или просто воспользуйтесь кнопкой.
                    '''
                ),
            )
            return 'CLIENT'
    else:
        phonenumber = update.message.contact.phone_number
        if phonenumber[0] != '+':
            phonenumber = f'+{phonenumber}'
    db.update_client_phone(telegram_id=update.effective_chat.id, phonenumber=phonenumber)
    context.bot.send_message(
            update.effective_chat.id,
            'Номер сохранен',
            reply_markup=ReplyKeyboardRemove()
        )
    return finish_request(redis=redis, update=update, context=context)


def finish_request(redis: Redis, update: Update, context: CallbackContext) -> str:
    message = redis.get(f'{update.effective_chat.id}_message')
    db.create_request(telegram_id=update.effective_chat.id, message=message)
    redis.delete(f'{update.effective_chat.id}_message')
    context.bot.send_message(
        update.effective_chat.id,
        dedent(
            f'''
            Заявка отправлена!
            Ожидайте звонка менеджера!
            '''
        ),
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
                        CallbackQueryHandler(new_client, pattern='new_customer'),
                        CallbackQueryHandler(new_contractor, pattern='new_contractor'),
                        CallbackQueryHandler(cancel_new_contractor, pattern='cancel_new_contractor'),
                        CallbackQueryHandler(contractor_salary, pattern='contractor_salary')
                    ],
                    'NEW_CONTRACTOR_FORM': [

                    ],
                    'CLIENT': [
                        MessageHandler(filters=Filters.regex(r'^\+?\d{7,15}$'), callback=partial(enter_phone, redis)),
                        MessageHandler(filters=Filters.contact, callback=partial(enter_phone, redis)),
                        MessageHandler(filters=Filters.text, callback=partial(client_message, redis)),
                        CallbackQueryHandler(new_request, pattern='new_request'),
                        CallbackQueryHandler(partial(cancel_new_request, redis), pattern='cancel_new_request'),
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