import os
import re

from contextlib import suppress
from functools import partial
from textwrap import dedent
from time import sleep
from uuid import uuid4

from django.core.management.base import BaseCommand
from django.utils.timezone import datetime, make_aware
from environs import Env
from more_itertools import chunked
from phonenumber_field.validators import (
    validate_international_phonenumber,
    ValidationError
)
from redis import Redis
from telegram import (
    ReplyKeyboardRemove,
    Update,
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
import main.management.commands.keyboards as keyboards


def delete_prev_inline(func, *args, **kwargs):
    def wrapper(*args, **kwargs):
        try:
            update, context = args[-2:]
        except ValueError:
            update, context = kwargs['update'], kwargs['context']
        if update.callback_query:
            with suppress(BadRequest):
                # Just in case if decorator handle message with callback and with no inline keyboard 
                # or any telegram error which is not critical for other functions
                context.bot.edit_message_reply_markup(
                    chat_id=update.effective_chat.id,
                    message_id=update.callback_query.message.message_id,
                )
        return func(*args, **kwargs)
    return wrapper


def check_client_subscription(func, *args, **kwargs):
    def wrapper(*args, **kwargs):
        try:
            update, context = args[-2:]
        except ValueError:
            update, context = kwargs['update'], kwargs['context']
        if db.is_actual_client_subscription(client_telegram_id=update.effective_chat.id):
            return func(*args, **kwargs)
        else:
            return subscription_alert(update=update, context=context)
    return wrapper


def check_available_client_request(func, *args, **kwargs):
    def wrapper(*args, **kwargs):
        try:
            update, context = args[-2:]
        except ValueError:
            update, context = kwargs['update'], kwargs['context']
        if db.is_available_client_request(client_telegram_id=update.effective_chat.id):
            return func(*args, **kwargs)
        else:
            return available_requests_alert(update=update, context=context)
    return wrapper


def send_message_all_managers(message: str,
                              update: Update,
                              context: CallbackContext) -> None:
    for manager_id in db.get_managers_telegram_ids():
        context.bot.send_message(
            manager_id,
            message
        )


@delete_prev_inline
def start(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        messages.WELCOME,
        reply_markup=ReplyKeyboardRemove()
    )
    if not db.get_person(telegram_id=update.effective_chat.id):
        return hello_visitor(update=update, context=context)
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.CHECK_ROLE,
        reply_markup=keyboards.START_INLINE
    )
    return 'VISITOR'


@delete_prev_inline
def check_access(update: Update, context: CallbackContext) -> str:
    _, claimed_role = update.callback_query.data.split(":::")

    if claimed_role == 'contractor':
        if db.is_contractor(telegram_id=update.effective_chat.id):
            return contractor_main(update=update, context=context)
        else:
            context.bot.send_message(
                update.effective_chat.id,
                text=messages.NOT_CONTRACTOR,
                reply_markup=keyboards.BECOME_CONTRACTOR_INLINE
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
        reply_markup=keyboards.SUBSCRIPTION_KEYBOARD
    )
    return 'CLIENT'


def hello_visitor(update: Update, context: CallbackContext) -> str:
    context.bot.send_document(
        chat_id=update.effective_chat.id,
        document=open('privacy_policy.pdf', 'rb'),
        caption=messages.HELLO_VISITOR,
        reply_markup=keyboards.PHONE_REQUEST_MARKUP,
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

    username = update.effective_chat.first_name \
        or update.effective_chat.username \
        or update.effective_chat.last_name
    db.create_person(
        telegram_id=update.effective_chat.id,
        username=username,
        phonenumber=phonenumber
    )
    context.bot.send_message(
            update.effective_chat.id,
            messages.REGISTRATION_COMPLETE,
            reply_markup=ReplyKeyboardRemove()
        )
    return start(update=update, context=context)


@delete_prev_inline
def new_client(update: Update, context: CallbackContext) -> str:
    db.create_client(telegram_id=update.effective_chat.id)
    return client_main(update=update, context=context)


@delete_prev_inline
def client_main(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.CLIENT_MAIN,
        reply_markup=keyboards.CLIENT_INLINE_KEYBOARD
    )
    return 'CLIENT'


@delete_prev_inline
@check_client_subscription
@check_available_client_request
def new_request(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.DESCRIBE_REQUEST,
        reply_markup=keyboards.CANCEL_INLINE
    )
    return 'CLIENT_NEW_REQUEST'


@delete_prev_inline
@check_client_subscription
@check_available_client_request
def client_request_description(update: Update, context: CallbackContext) -> str:
    if len(update.message.text) > 1000:
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.TOO_MUCH_REQUEST_SYMBOLS,
            reply_markup=keyboards.CANCEL_INLINE
        )
        return 'CLIENT_NEW_REQUEST'

    order = db.create_order(
        telegram_id=update.effective_chat.id,
        description=update.message.text
    )
    send_message_all_managers(
        message=messages.new_order_notification(order=order),
        update=update,
        context=context
    )
    context.bot.send_message(
        update.effective_chat.id,
        messages.SUCCESS_REQUEST
    )
    sleep(2)
    return client_main(update=update, context=context)


@delete_prev_inline
def display_current_orders(update: Update, context: CallbackContext) -> str:
    orders = db.get_current_client_orders(telegram_id=update.effective_chat.id)
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.display_orders(orders=orders),
        reply_markup=keyboards.client_orders_inline(orders=orders)
    )
    return 'CLIENT'


@delete_prev_inline
def display_order(update: Update, context: CallbackContext) -> str:
    _, order_id = update.callback_query.data.split(':::')
    order = db.get_order(order_id=int(order_id))
    context.bot.send_message(
        update.effective_chat.id,
        text=order.display(),
        reply_markup=keyboards.client_order_inline(
            order=order,
            can_see_contractor_contact=db.can_see_contractor_contacts(
                telegram_id=update.effective_chat.id
            )
        )
    )
    return 'CLIENT'


@delete_prev_inline
def add_order_comment(redis: Redis, update: Update, context: CallbackContext) -> str:
    _, order_id = update.callback_query.data.split(':::')
    redis.set(f'{update.effective_chat.id}_order_id', order_id)
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NEW_CLIENT_COMMENT,
        reply_markup=keyboards.CANCEL_INLINE
    )
    return 'CLIENT_NEW_COMMENT'


@delete_prev_inline
def client_comment_description(redis: Redis, update: Update, context: CallbackContext) -> str:
    if len(update.message.text) > 1000:
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.TOO_MUCH_REQUEST_SYMBOLS,
            reply_markup=keyboards.CANCEL_INLINE
        )
        return 'CLIENT_NEW_COMMENT'
    order_id = redis.get(f'{update.effective_chat.id}_order_id')
    order, comment = db.create_comment_from_client(
        order_id=int(order_id),
        comment=update.message.text
    )
    send_message_all_managers(
        message=messages.new_client_comment_notification(order=order, comment=comment),
        update=update,
        context=context
    )
    context.bot.send_message(
        update.effective_chat.id,
        messages.SUCCESS_COMMENT
    )
    redis.delete(f'{update.effective_chat.id}_order_id')
    sleep(2)
    return client_main(update=update, context=context)


@delete_prev_inline
def add_order_complaint(redis: Redis, update: Update, context: CallbackContext) -> str:
    _, order_id = update.callback_query.data.split(':::')
    redis.set(f'{update.effective_chat.id}_order_id', order_id)
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NEW_CLIENT_COMMENT,
        reply_markup=keyboards.CANCEL_INLINE
    )
    return 'CLIENT_NEW_COMPLAINT'


@delete_prev_inline
def client_complaint_description(redis: Redis, update: Update, context: CallbackContext) -> str:
    if len(update.message.text) > 1000:
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.TOO_MUCH_REQUEST_SYMBOLS,
            reply_markup=keyboards.CANCEL_INLINE
        )
        return 'CLIENT_NEW_COMPLAINT'
    order_id = redis.get(f'{update.effective_chat.id}_order_id')
    order, complaint = db.create_client_order_complaint(
        order_id=int(order_id),
        complaint=update.message.text
    )
    send_message_all_managers(
        message=messages.new_client_complaint_notification(order=order, complaint=complaint),
        update=update,
        context=context
    )
    context.bot.send_message(
        update.effective_chat.id,
        messages.SUCCESS_COMPLAINT
    )
    redis.delete(f'{update.effective_chat.id}_order_id')
    sleep(2)
    return client_main(update=update, context=context)


@delete_prev_inline
def send_contractor_contact(update: Update, context: CallbackContext) -> str:
    _, order_id = update.callback_query.data.split(':::')
    try:
        contractor_contact_meta = db.get_order_contractor_contact(order_id=int(order_id))
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
        text=client_tariff_info or messages.NO_ACTIVE_SUBSCRIPTIONS
    )
    sleep(2)
    return client_main(update=update, context=context)


@delete_prev_inline
def new_contractor(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NEW_CONTRACTOR,
        reply_markup=keyboards.CANCEL_INLINE
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
    contractor = db.create_contractor(
        telegram_id=update.effective_chat.id,
        comment=update.message.text
    )
    send_message_all_managers(
        message=messages.new_contractor_notification(contractor=contractor, message=update.message.text),
        update=update,
        context=context
    )
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.NEW_CONTRACTOR_CREATED
    )
    return start(update=update, context=context)


@delete_prev_inline
def contractor_main(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.CONTRACTOR_MAIN,
        reply_markup=keyboards.CONTRACTOR_INLINE_KEYBOARD
    )
    return 'CONTRACTOR'


@delete_prev_inline
def contractor_display_orders(update: Update, context: CallbackContext) -> str:
    callback_data = update.callback_query.data
    contractor = db.get_contractor(telegram_id=update.effective_chat.id)
    if callback_data == buttons.CONTRACTOR_CURRENT_ORDERS['callback_data']:
        orders = contractor.get_current_orders()
        if orders:
            message = messages.display_orders(orders=orders, are_current=True)
            keyboard = keyboards.contractor_orders_inline(orders=orders, are_current_orders=True)
        else:
            no_order_message = messages.NO_ACTIVE_ORDERS
    elif callback_data == buttons.CONTRACTOR_AVAILABLE_ORDERS['callback_data']:
        orders = db.get_contractor_available_orders(telegram_id=update.effective_chat.id)
        if orders:
            message = messages.display_orders(orders=orders, are_current=True)
            keyboard = keyboards.contractor_orders_inline(orders=orders, are_available_orders=True)
        else:
            no_order_message = messages.NO_AVAILABLE_ORDERS
    if not orders:
        context.bot.send_message(
            update.effective_chat.id,
            text=no_order_message,
        )
        sleep(2)
        return contractor_main(update=update, context=context)

    context.bot.send_message(
        update.effective_chat.id,
        text=message,
        reply_markup=keyboard
    )
    return 'CONTRACTOR'


@delete_prev_inline
def contractor_display_order(update: Update, context: CallbackContext) -> str:
    callback, order_id = update.callback_query.data.split(':::')
    order = db.get_order(order_id=int(order_id))
    if callback == buttons.AVAILABLE_ORDER['callback_data']:
        keyboard = keyboards.contractor_order_inline(order=order, is_available=True)
    elif callback == buttons.CURRENT_ORDER['callback_data']:
        keyboard = keyboards.contractor_order_inline(order=order, is_current=True)
    context.bot.send_message(
        update.effective_chat.id,
        order.display(),
        reply_markup=keyboard
    )
    return 'CONTRACTOR'


@delete_prev_inline
def contractor_take_order(update: Update, context: CallbackContext) -> str:
    _, order_id = update.callback_query.data.split(':::')
    order = db.set_order_contractor(telegram_id=update.effective_chat.id, order_id=order_id)
    send_message_all_managers(
        message=messages.contractor_took_order_notification(order=order),
        update=update,
        context=context
    )
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.APPROVE_ORDER_CONTRACTOR
    )
    return contractor_main(update=update, context=context)


@delete_prev_inline
def contractor_finish_order(update: Update, context: CallbackContext) -> str:
    _, order_id = update.callback_query.data.split(':::')
    order = db.close_order(order_id=int(order_id))
    send_message_all_managers(
        message=messages.contractor_finished_order_notification(order=order),
        update=update,
        context=context
    )
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.ORDER_CLOSED
    )
    return contractor_main(update=update, context=context)


@delete_prev_inline
def contractor_set_estimate_datetime(redis: Redis, update: Update, context: CallbackContext) -> str:
    _, order_id = update.callback_query.data.split(':::')
    redis.set(f'{update.effective_chat.id}_contractor_order_id', order_id)
    context.bot.send_message(
        update.effective_chat.id,
        messages.SET_ESTIMATE_DATETIME,
        reply_markup=keyboards.BACK_TO_CONTRACTOR_MAIN
    )
    return 'CONTACTOR_SET_ESTIMATE_DATETIME'


@delete_prev_inline
def contractor_enter_estimate_datetime(redis: Redis, update: Update, context: CallbackContext) -> str:
    separators = r'[:,. -!]'
    datetime_regex = r'\d{4}[:,. -!]\d{2}[:,. -!]\d{2}[:,. -!]\d{2}[:,. -!]\d{2}'
    try:
        if not re.match(datetime_regex, update.message.text):
            raise ValueError
        year, month, day, hour, minute = re.split(separators, update.message.text)
        estimate_datetime = make_aware(
            # here can be ValueError
            datetime(int(year), int(month), int(day), int(hour), int(minute), 0, 0)
        )
        order_id = redis.get(f'{update.effective_chat.id}_contractor_order_id')
        order = db.set_estimate_datetime(order_id=int(order_id), estimate_datetime=estimate_datetime)
        send_message_all_managers(
            message=messages.contractor_set_estimate_datetime_notifiction(order=order),
            update=update,
            context=context
        )
        redis.delete(f'{update.effective_chat.id}_contractor_order_id')
        return contractor_main(update=update, context=context)
    except ValueError:
        context.bot.send_message(
            update.effective_chat.id,
            messages.SET_ESTIMATE_DATETIME,
            reply_markup=keyboards.BACK_TO_CONTRACTOR_MAIN
        )
        return 'CONTACTOR_SET_ESTIMATE_DATETIME'

@delete_prev_inline
def contractor_display_salary(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        text=db.get_contractor_salary(telegram_id=update.effective_chat.id),
        reply_markup=keyboards.CONTRACTOR_INLINE_KEYBOARD
    )
    return 'CONTRACTOR'


@delete_prev_inline
def tell_about_subscription(update: Update, context: CallbackContext) -> str:
    context.bot.send_message(
        update.effective_chat.id,
        messages.tell_about_subscription(tariffs=tariffs),
        reply_markup=keyboards.subscriptions_inline(tariffs=db.get_tariffs())
    )
    return 'SUBSCRIPTION'


def activate_subscription(redis: Redis, update: Update, context: CallbackContext) -> str:
    _, tariff_id = update.callback_query.data.split(":")
    tariff = db.get_tariff(tariff_id=tariff_id)
    payload = str(uuid4())
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
    subscription = db.create_subscription(
        telegram_id=telegram_id,
        tariff_id=tariff_id,
        payment_id=payload
    )
    send_message_all_managers(
        message=messages.new_subscription_notification(subscription=subscription),
        update=update,
        context=context
    )


class Command(BaseCommand):
    help = "Start Telegram bot"

    def handle(self, *args, **kwargs):

        env = Env()
        env.read_env()

        updater = Updater(token=env.str('TELEGRAM_BOT_TOKEN'), use_context=True)
        redis = Redis(
            host=env.str('REDIS_HOST', 'localhost'),
            port=env.int('REDIS_PORT', 6379),
            db=env.int('REDIS_DB', 0),
            password=env.str('REDIS_PASSWORD', None),
            decode_responses=True
        )

        updater.dispatcher.add_handler(
            ConversationHandler(
                entry_points=[
                    CommandHandler('start', start),
                    MessageHandler(filters=Filters.all, callback=start),
                    CallbackQueryHandler(callback=start)
                ],
                states={
                    'VISITOR': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(check_access, pattern=buttons.CHECK_ACCESS_CALLBACK),
                        CallbackQueryHandler(start, pattern=buttons.CHANGE_ROLE['callback_data']),
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
                        CallbackQueryHandler(start, pattern=buttons.CANCEL['callback_data']),
                        PreCheckoutQueryHandler(partial(confirm_payment, redis)),
                        MessageHandler(Filters.successful_payment, client_main)
                    ],
                    'NEW_CONTRACTOR': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(start, pattern=buttons.CANCEL['callback_data']),
                        MessageHandler(Filters.text, new_contractor_message)
                    ],
                    'CLIENT': [
                        CallbackQueryHandler(start, pattern=buttons.CHANGE_ROLE['callback_data']),
                        CommandHandler('start', start),
                        CallbackQueryHandler(new_request, pattern=buttons.NEW_REQUEST['callback_data']),
                        CallbackQueryHandler(display_current_orders, pattern=buttons.CLIENT_CURRENT_ORDERS['callback_data']),
                        CallbackQueryHandler(display_order, pattern=buttons.ORDER['callback_data']),
                        CallbackQueryHandler(partial(add_order_comment, redis), pattern=buttons.ORDER_COMMENT['callback_data']),
                        CallbackQueryHandler(partial(add_order_complaint, redis), pattern=buttons.ORDER_COMPLAINT['callback_data']),
                        CallbackQueryHandler(send_contractor_contact, pattern=buttons.CONTRACTOR_CONTACTS['callback_data']),
                        CallbackQueryHandler(send_current_tariff, pattern=buttons.CLIENT_CURRENT_TARIFF['callback_data']),
                        CallbackQueryHandler(new_contractor, pattern=buttons.NEW_CONTRACTOR['callback_data']),
                        CallbackQueryHandler(client_main, pattern=buttons.CANCEL['callback_data']),
                        CallbackQueryHandler(tell_about_subscription, pattern=buttons.CREATE_SUBSCRIPTION['callback_data']),
                        CallbackQueryHandler(client_main, pattern=buttons.BACK_TO_CLIENT_MAIN['callback_data']),
                    ],
                    'CLIENT_NEW_REQUEST': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.text, callback=client_request_description),
                        CallbackQueryHandler(client_main, pattern=buttons.CANCEL['callback_data']),

                    ],
                    'CLIENT_NEW_COMMENT': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.text, callback=partial(client_comment_description, redis)),
                        CallbackQueryHandler(client_main, pattern=buttons.CANCEL['callback_data']),

                    ],
                    'CLIENT_NEW_COMPLAINT': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.text, callback=partial(client_complaint_description, redis)),
                        CallbackQueryHandler(client_main, pattern=buttons.CANCEL['callback_data']),

                    ],
                    'CONTRACTOR': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(start, pattern=buttons.CHANGE_ROLE['callback_data']),
                        CallbackQueryHandler(contractor_display_orders, pattern=buttons.CONTRACTOR_CURRENT_ORDERS['callback_data']),
                        CallbackQueryHandler(contractor_display_orders, pattern=buttons.CONTRACTOR_AVAILABLE_ORDERS['callback_data']),
                        CallbackQueryHandler(contractor_display_order, pattern=buttons.CURRENT_ORDER['callback_data']),
                        CallbackQueryHandler(contractor_display_order, pattern=buttons.AVAILABLE_ORDER['callback_data']),
                        CallbackQueryHandler(contractor_take_order, pattern=buttons.TAKE_ORDER['callback_data']),
                        CallbackQueryHandler(contractor_finish_order, pattern=buttons.FINISH_ORDER['callback_data']),
                        CallbackQueryHandler(partial(contractor_set_estimate_datetime, redis), pattern=buttons.CONTRACTOR_SET_ESTIMATE_DATETIME['callback_data']),
                        CallbackQueryHandler(contractor_display_salary, pattern=buttons.CONTRACTOR_SALARY['callback_data']),
                        CallbackQueryHandler(contractor_main, pattern=buttons.BACK_TO_CONTRACTOR_MAIN['callback_data']),
                    ],
                    'CONTACTOR_SET_ESTIMATE_DATETIME': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(contractor_main, pattern=buttons.BACK_TO_CONTRACTOR_MAIN['callback_data']),
                        MessageHandler(filters=Filters.text, callback=partial(contractor_enter_estimate_datetime, redis)),
                    ],
                },
                fallbacks=[],
            )
        )

        updater.dispatcher.add_handler(PreCheckoutQueryHandler(partial(confirm_payment, redis)))

        updater.start_polling()
        updater.idle()