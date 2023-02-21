from pydoc import visiblename
from textwrap import dedent
from django.core.management.base import BaseCommand
from environs import Env

from telegram import (
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
    ConversationHandler
)

import main.management.commands.db_processing as db


VISITOR_INLINE_KEYBOARD = InlineKeyboardMarkup(
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


def check_access(update: Update, context: CallbackContext) -> str:
    role = db.get_role(telegram_id=update.effective_chat.id)
    if role == 'admin':
        # send smth to admin

        return 'ADMIN'
    elif role == 'contractor':
        # send smth to contractor

        return 'CONTRACTOR'
    elif role == 'client':
        # send smth to client

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


def new_request(update: Update, context: CallbackContext) -> str:
    return 'VISITOR'


def new_contractor(update: Update, context: CallbackContext) -> str:
    context.bot.edit_message_reply_markup(
        chat_id=update.effective_chat.id,
        message_id=update.callback_query.message.message_id,
    )
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


def contractor_salary(update: Update, context: CallbackContext) -> str:
    context.bot.edit_message_reply_markup(
        chat_id=update.effective_chat.id,
        message_id=update.callback_query.message.message_id,
    )
    context.bot.send_message(
        update.effective_chat.id,
        text='Вы будете зарабатывать МНОГО ДЕНЕГ!!! 💰💰💰',
        reply_markup=NEW_CONTRUCTOR_INLINE_KEYBOARD
    )
    return 'VISITOR'


def cancel_new_contractor(update: Update, context: CallbackContext) -> str:
    context.bot.edit_message_reply_markup(
        chat_id=update.effective_chat.id,
        message_id=update.callback_query.message.message_id,
    )
    context.bot.send_message(
        update.effective_chat.id,
        text='Как скажете',
        reply_markup=VISITOR_INLINE_KEYBOARD
    )
    return 'VISITOR'


class Command(BaseCommand):
    help = "Start Telegram bot"

    def handle(self, *args, **kwargs):

        env = Env()
        env.read_env()

        updater = Updater(token=env.str('TELEGRAM_BOT_TOKEN'), use_context=True)

        updater.dispatcher.add_handler(
            ConversationHandler(
                entry_points = [
                    CommandHandler('start', check_access)
                ],
                states = {
                    'VISITOR': [
                        CallbackQueryHandler(new_request, pattern='new_request'),
                        CallbackQueryHandler(new_contractor, pattern='new_contractor'),
                        CallbackQueryHandler(cancel_new_contractor, pattern='cancel_new_contractor'),
                        CallbackQueryHandler(contractor_salary, pattern='contractor_salary')

                    ],
                    'NEW_CONTRACTOR_FORM': [

                    ],
                    'CUSTOMER': [

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