import os
import re
import logging
import uuid
import json
import requests
from yookassa import Configuration, Payment

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
    Contact,
    InlineKeyboardMarkup,
    InlineKeyboardButton
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

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
def select_category(update: Update, context: CallbackContext) -> str:
    """Показывает список категорий услуг"""
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.SELECT_CATEGORY_MESSAGE,
        reply_markup=keyboards.get_categories_keyboard()
    )
    return 'CLIENT_SELECT_CATEGORY'


@delete_prev_inline
def show_category_services(update: Update, context: CallbackContext) -> str:
    """Показывает услуги в выбранной категории"""
    category_id = int(update.callback_query.data.split(':')[1])
    
    # Сохраняем ID категории в контексте
    context.user_data['selected_category_id'] = category_id
    
    # Получаем категорию
    categories = db.get_service_categories()
    category = next((c for c in categories if c.id == category_id), None)
    
    if not category:
        return client_main(update, context)
    
    # Отправляем сообщение с услугами в категории
    context.bot.send_message(
        update.effective_chat.id,
        text=f"Услуги в категории: <b>{category.name}</b>",
        parse_mode='HTML',
        reply_markup=keyboards.get_services_keyboard(category_id)
    )
    
    return 'CLIENT_BROWSE_SERVICES'


@delete_prev_inline
def show_service_details(update: Update, context: CallbackContext) -> str:
    """Показывает детальную информацию об услуге"""
    service_id = int(update.callback_query.data.split(':')[1])
    
    # Сохраняем ID услуги в контексте
    context.user_data['selected_service_id'] = service_id
    
    # Получаем услугу из базы данных
    from main.models import Service
    try:
        service = Service.objects.get(id=service_id)
        
        # Формируем сообщение с деталями услуги и информацией о фрилансере
        message = f"""
<b>{service.title}</b>

<b>Описание:</b> {service.description}

<b>Цена:</b> {service.price} руб.

<b>Фрилансер:</b> {service.contractor.person.name}
"""
        
        # Отправляем сообщение с фото, если оно есть и файл существует
        if service.photo and os.path.exists(service.photo.path):
            try:
                context.bot.send_photo(
                    update.effective_chat.id,
                    photo=open(service.photo.path, 'rb'),
                    caption=message,
                    parse_mode='HTML',
                    reply_markup=keyboards.get_service_details_keyboard(service_id)
                )
            except Exception as e:
                logging.error(f"Ошибка при отправке фото: {e}")
                # Если не удалось отправить фото, отправляем только текст
                context.bot.send_message(
                    update.effective_chat.id,
                    text=message,
                    parse_mode='HTML',
                    reply_markup=keyboards.get_service_details_keyboard(service_id)
                )
        else:
            context.bot.send_message(
                update.effective_chat.id,
                text=message,
                parse_mode='HTML',
                reply_markup=keyboards.get_service_details_keyboard(service_id)
            )
        
        return 'CLIENT_SERVICE_DETAILS'
    
    except Service.DoesNotExist:
        context.bot.send_message(
            update.effective_chat.id,
            text="Услуга не найдена. Пожалуйста, выберите другую услугу."
        )
        return show_category_services(update, context)


@delete_prev_inline
def add_to_cart(update: Update, context: CallbackContext) -> str:
    """Добавляет услугу в корзину"""
    service_id = int(update.callback_query.data.split(':')[1])
    
    # Добавляем услугу в набор
    db.add_service_to_set(update.effective_user.id, service_id)
    
    # Отправляем сообщение об успешном добавлении
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.ADDED_TO_CART_MESSAGE
    )
    
    # Показываем корзину
    return show_cart(update, context)


@delete_prev_inline
def show_cart(update: Update, context: CallbackContext) -> str:
    """Показывает содержимое корзины"""
    # Получаем набор услуг пользователя
    service_set = db.get_client_service_set(update.effective_user.id)
    
    if not service_set or not service_set.services.exists():
        # Если корзина пуста
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.CART_EMPTY_MESSAGE,
            reply_markup=keyboards.get_categories_keyboard()
        )
        return 'CLIENT_SELECT_CATEGORY'
    
    # Формируем список услуг в корзине
    services_text = ""
    for service in service_set.services.all():
        services_text += f"• {service.title} - {service.get_final_price()} руб.\n"
    
    # Рассчитываем общую стоимость
    total_price = service_set.get_total_price()
    
    # Проверяем, есть ли скидка
    discount_text = ""
    if service_set.services.count() >= 3:
        discount_text = " (включая скидку 10%)"
    
    # Отправляем сообщение с корзиной
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.CART_TEMPLATE.format(
            services=services_text,
            total_price=total_price,
            discount=discount_text
        ),
        parse_mode='HTML',
        reply_markup=keyboards.get_cart_keyboard(update.effective_user.id)
    )
    
    return 'CLIENT_CART'


@delete_prev_inline
def remove_from_cart(update: Update, context: CallbackContext) -> str:
    """Удаляет услугу из корзины"""
    service_id = int(update.callback_query.data.split(':')[1])
    
    # Получаем набор услуг пользователя
    service_set = db.get_client_service_set(update.effective_user.id)
    
    if service_set:
        # Удаляем услугу из набора
        from main.models import Service
        try:
            service = Service.objects.get(id=service_id)
            service_set.services.remove(service)
            
            # Отправляем сообщение об успешном удалении
            context.bot.send_message(
                update.effective_chat.id,
                text=messages.REMOVED_FROM_CART_MESSAGE
            )
        except Service.DoesNotExist:
            pass
    
    # Показываем обновленную корзину
    return show_cart(update, context)


@delete_prev_inline
def clear_cart(update: Update, context: CallbackContext) -> str:
    """Очищает корзину"""
    # Очищаем набор услуг пользователя
    db.clear_service_set(update.effective_user.id)
    
    # Отправляем сообщение об успешной очистке
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.CART_CLEARED_MESSAGE
    )
    
    # Возвращаемся к выбору категорий
    return select_category(update, context)


@delete_prev_inline
def checkout(update: Update, context: CallbackContext) -> str:
    """Перенаправляет клиента на сайт консалтинговой фирмы для оплаты"""
    # Получаем набор услуг пользователя
    service_set = db.get_client_service_set(update.effective_user.id)
    
    if not service_set or not service_set.services.exists():
        # Если корзина пуста
        context.bot.send_message(
            update.effective_chat.id,
            text="Ваша корзина пуста. Добавьте услуги перед оформлением заказа."
        )
        return select_category(update, context)
    
    # Формируем список услуг в корзине для отображения
    services_text = ""
    for service in service_set.services.all():
        services_text += f"• {service.title} - {service.get_final_price()} руб.\n"
    
    # Рассчитываем общую стоимость
    total_price = service_set.get_total_price()
    
    # Проверяем, есть ли скидка
    discount_text = ""
    if service_set.services.count() >= 3:
        discount_text = " (включая скидку 10%)"
    
    # Создаем уникальный идентификатор заказа
    order_id = str(uuid.uuid4())
    
    # Формируем URL для оплаты на сайте консалтинговой фирмы
    payment_url = f"https://consulting-firm.com/payment?order_id={order_id}&amount={total_price}"
    
    # Отправляем сообщение с информацией о заказе и ссылкой на оплату
    context.bot.send_message(
        update.effective_chat.id,
        text=f"""
<b>Ваш заказ:</b>

{services_text}
<b>Итого:</b> {total_price} руб.{discount_text}

Для оплаты перейдите по ссылке ниже:
{payment_url}

После оплаты исполнители свяжутся с вами в ближайшее время.
""",
        parse_mode='HTML'
    )
    
    # Отмечаем набор как отправленный на оплату
    from django.utils.timezone import now
    service_set.paid_at = now()
    service_set.save()
    
    # Возвращаемся на главную
    return client_main(update, context)


@delete_prev_inline
def contractor_services(update: Update, context: CallbackContext) -> str:
    """Показывает услуги исполнителя"""
    # Получаем услуги исполнителя
    services = db.get_contractor_services(update.effective_user.id)
    
    if not services.exists():
        # Если у исполнителя нет услуг
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.CONTRACTOR_SERVICES_EMPTY,
            reply_markup=keyboards.get_contractor_services_keyboard(update.effective_user.id)
        )
    else:
        # Отправляем сообщение со списком услуг
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.CONTRACTOR_SERVICES_MESSAGE,
            parse_mode='HTML',
            reply_markup=keyboards.get_contractor_services_keyboard(update.effective_user.id)
        )
    
    return 'CONTRACTOR_SERVICES'


@delete_prev_inline
def add_service_start(update: Update, context: CallbackContext) -> str:
    """Начинает процесс добавления услуги"""
    # Очищаем данные о новой услуге
    context.user_data['new_service'] = {}
    
    # Запрашиваем название услуги
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.ADD_SERVICE_TITLE_MESSAGE,
        reply_markup=keyboards.CANCEL_INLINE
    )
    
    return 'CONTRACTOR_ADD_SERVICE_TITLE'


@delete_prev_inline
def add_service_title(update: Update, context: CallbackContext) -> str:
    """Сохраняет название услуги и запрашивает описание"""
    # Сохраняем название
    context.user_data['new_service']['title'] = update.message.text
    
    # Запрашиваем описание
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.ADD_SERVICE_DESCRIPTION_MESSAGE,
        reply_markup=keyboards.CANCEL_INLINE
    )
    
    return 'CONTRACTOR_ADD_SERVICE_DESCRIPTION'


@delete_prev_inline
def add_service_description(update: Update, context: CallbackContext) -> str:
    """Сохраняет описание услуги и запрашивает цену"""
    # Сохраняем описание
    context.user_data['new_service']['description'] = update.message.text
    
    # Запрашиваем цену
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.ADD_SERVICE_PRICE_MESSAGE,
        reply_markup=keyboards.CANCEL_INLINE
    )
    
    return 'CONTRACTOR_ADD_SERVICE_PRICE'


@delete_prev_inline
def add_service_price(update: Update, context: CallbackContext) -> str:
    """Сохраняет цену услуги и запрашивает категорию"""
    try:
        # Пытаемся преобразовать введенный текст в число
        price = float(update.message.text)
        
        # Сохраняем цену
        context.user_data['new_service']['price'] = price
        
        # Запрашиваем категорию
        context.bot.send_message(
            update.effective_chat.id,
            text="Выберите категорию услуги:",
            reply_markup=keyboards.get_categories_keyboard()
        )
        
        return 'CONTRACTOR_ADD_SERVICE_CATEGORY'
    
    except ValueError:
        # Если введено не число
        context.bot.send_message(
            update.effective_chat.id,
            text="Пожалуйста, введите корректную цену (только число):",
            reply_markup=keyboards.CANCEL_INLINE
        )
        
        return 'CONTRACTOR_ADD_SERVICE_PRICE'


@delete_prev_inline
def add_service_category(update: Update, context: CallbackContext) -> str:
    """Сохраняет категорию услуги и запрашивает фото"""
    category_id = int(update.callback_query.data.split(':')[1])
    
    # Сохраняем категорию
    context.user_data['new_service']['category_id'] = category_id
    
    # Запрашиваем фото
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.ADD_SERVICE_PHOTO_MESSAGE,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Пропустить", callback_data="skip_photo")
        ]])
    )
    
    return 'CONTRACTOR_ADD_SERVICE_PHOTO'


@delete_prev_inline
def add_service_photo(update: Update, context: CallbackContext) -> str:
    """Сохраняет фото услуги и создает услугу"""
    # Проверяем, есть ли фото
    if update.message and update.message.photo:
        # Получаем файл с наибольшим разрешением
        photo = update.message.photo[-1]
        file = context.bot.get_file(photo.file_id)
        
        # Создаем директорию для фото, если её нет
        import os
        os.makedirs('media/service_photos', exist_ok=True)
        
        # Генерируем уникальное имя файла
        from uuid import uuid4
        filename = f"service_photos/{uuid4()}.jpg"
        
        # Скачиваем фото
        file.download(f'media/{filename}')
        
        # Сохраняем путь к фото
        context.user_data['new_service']['photo'] = filename
    
    # Создаем услугу
    db.create_service(
        contractor_id=update.effective_user.id,
        title=context.user_data['new_service']['title'],
        description=context.user_data['new_service']['description'],
        price=context.user_data['new_service']['price'],
        category_id=context.user_data['new_service']['category_id'],
        photo=context.user_data['new_service'].get('photo')
    )
    
    # Отправляем сообщение об успешном создании
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.SERVICE_ADDED_MESSAGE
    )
    
    # Очищаем данные о новой услуге
    context.user_data.pop('new_service', None)
    
    # Показываем услуги исполнителя
    return contractor_services(update, context)


@delete_prev_inline
def skip_photo(update: Update, context: CallbackContext) -> str:
    """Пропускает добавление фото и создает услугу"""
    # Создаем услугу без фото
    db.create_service(
        contractor_id=update.effective_user.id,
        title=context.user_data['new_service']['title'],
        description=context.user_data['new_service']['description'],
        price=context.user_data['new_service']['price'],
        category_id=context.user_data['new_service']['category_id']
    )
    
    # Отправляем сообщение об успешном создании
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.SERVICE_ADDED_MESSAGE
    )
    
    # Очищаем данные о новой услуге
    context.user_data.pop('new_service', None)
    
    # Показываем услуги исполнителя
    return contractor_services(update, context)


@delete_prev_inline
def edit_service(update: Update, context: CallbackContext) -> str:
    """Показывает меню редактирования услуги"""
    service_id = int(update.callback_query.data.split(':')[1])
    
    # Сохраняем ID услуги в контексте
    context.user_data['edit_service_id'] = service_id
    
    # Получаем услугу из базы данных
    from main.models import Service
    try:
        service = Service.objects.get(id=service_id)
        
        # Формируем сообщение с деталями услуги
        message = f"""
<b>{service.title}</b>

<b>Описание:</b> {service.description}

<b>Цена:</b> {service.price} руб.

<b>Категория:</b> {service.category.name if service.category else 'Не указана'}
"""
        
        # Отправляем сообщение с фото, если оно есть и файл существует
        if service.photo and os.path.exists(service.photo.path):
            try:
                context.bot.send_photo(
                    update.effective_chat.id,
                    photo=open(service.photo.path, 'rb'),
                    caption=message,
                    parse_mode='HTML',
                    reply_markup=keyboards.get_service_edit_keyboard(service_id)
                )
            except Exception as e:
                logging.error(f"Ошибка при отправке фото: {e}")
                # Если не удалось отправить фото, отправляем только текст
                context.bot.send_message(
                    update.effective_chat.id,
                    text=message,
                    parse_mode='HTML',
                    reply_markup=keyboards.get_service_edit_keyboard(service_id)
                )
        else:
            context.bot.send_message(
                update.effective_chat.id,
                text=message,
                parse_mode='HTML',
                reply_markup=keyboards.get_service_edit_keyboard(service_id)
            )
        
        return 'CONTRACTOR_EDIT_SERVICE'
    
    except Service.DoesNotExist:
        context.bot.send_message(
            update.effective_chat.id,
            text="Услуга не найдена. Пожалуйста, выберите другую услугу."
        )
        return contractor_services(update, context)


@delete_prev_inline
def delete_service_confirm(update: Update, context: CallbackContext) -> str:
    """Подтверждает удаление услуги"""
    service_id = int(update.callback_query.data.split(':')[1])
    
    # Сохраняем ID услуги в контексте
    context.user_data['delete_service_id'] = service_id
    
    # Запрашиваем подтверждение
    context.bot.send_message(
        update.effective_chat.id,
        text="Вы уверены, что хотите удалить эту услугу?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Да, удалить", callback_data="confirm_delete_service")],
            [InlineKeyboardButton("Нет, отменить", callback_data="cancel_delete_service")]
        ])
    )
    
    return 'CONTRACTOR_DELETE_SERVICE'


@delete_prev_inline
def confirm_delete_service(update: Update, context: CallbackContext) -> str:
    """Удаляет услугу"""
    service_id = context.user_data.get('delete_service_id')
    
    if service_id:
        # Удаляем услугу
        db.delete_service(service_id)
        
        # Отправляем сообщение об успешном удалении
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.SERVICE_DELETED_MESSAGE
        )
        
        # Очищаем ID услуги из контекста
        context.user_data.pop('delete_service_id', None)
    
    # Показываем услуги исполнителя
    return contractor_services(update, context)


@delete_prev_inline
def cancel_delete_service(update: Update, context: CallbackContext) -> str:
    """Отменяет удаление услуги"""
    # Очищаем ID услуги из контекста
    service_id = context.user_data.pop('delete_service_id', None)
    
    if service_id:
        # Возвращаемся к редактированию услуги
        context.user_data['edit_service_id'] = service_id
        return edit_service(update, context)
    
    # Показываем услуги исполнителя
    return contractor_services(update, context)


@delete_prev_inline
def switch_to_client(update: Update, context: CallbackContext) -> str:
    """Переключает пользователя из режима фрилансера в режим клиента"""
    # Проверяем, есть ли у пользователя профиль клиента
    try:
        db.get_client(update.effective_user.id)
    except db.EntityNotFoundError:
        # Если профиля клиента нет, создаем его
        db.create_client(update.effective_user.id)
    
    # Отправляем приветственное сообщение
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.CLIENT_WELCOME_MESSAGE
    )
    
    # Переходим на главную страницу клиента
    return client_main(update, context)


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
        text=messages.CONTRACTOR_WELCOME_MESSAGE,
        reply_markup=keyboards.CONTRACTOR_INLINE_KEYBOARD
    )
    return 'CONTRACTOR'


@delete_prev_inline
def contractor_display_orders(update: Update, context: CallbackContext) -> str:
    callback_data = update.callback_query.data
    contractor = db.get_contractor(telegram_id=update.effective_chat.id)
    
    # Обрабатываем только доступные заказы
    orders = db.get_contractor_available_orders(telegram_id=update.effective_chat.id)
    if orders:
        message = messages.display_orders(orders=orders, are_current=True)
        keyboard = keyboards.contractor_orders_inline(orders=orders, are_available_orders=True)
    else:
        no_order_message = messages.NO_AVAILABLE_ORDERS
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
    """Обработка ввода даты и времени выполнения заказа"""
    try:
        estimate_datetime_str = update.message.text
        day, month, year, hour, minute = re.findall(r'\d+', estimate_datetime_str)
        estimate_datetime = datetime(
            int(year), int(month), int(day), int(hour), int(minute), 0, 0
        )
        order_id = redis.get(f'{update.effective_chat.id}_contractor_order_id')
        order = db.set_estimate_datetime(order_id=int(order_id), estimate_datetime=estimate_datetime)
        
        # Отправляем уведомление клиенту
        context.bot.send_message(
            chat_id=order.subscription.client.person.telegram_id,
            text=messages.contractor_set_estimate_datetime_notifiction(order)
        )
        
        # Отправляем сообщение подрядчику
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Срок выполнения заказа установлен'
        )
        
        return contractor_main(update, context)
    except (ValueError, IndexError):
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text='Неверный формат даты. Пожалуйста, введите дату в формате ДД.ММ.ГГГГ ЧЧ:ММ'
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
    """Рассказывает о подписках"""
    tariffs = db.get_tariffs()
    message = messages.tell_about_subscription(tariffs=tariffs)
    keyboard = keyboards.subscriptions_inline(tariffs=tariffs)
    
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=message,
        reply_markup=keyboard
    )
    
    logger.debug('Sent subscription message with inline keyboard')
    return 'CLIENT'


def check_payment_status(update: Update, context: CallbackContext) -> None:
    """Проверяет статус платежа и активирует подписку если оплата прошла"""
    
    # Получаем payment_id из callback_data
    payment_id = update.callback_query.data.split(':')[1]
    
    # Инициализируем Redis
    env = Env()
    env.read_env()
    redis = Redis(
        host=env('REDIS_HOST', 'localhost'),
        port=env('REDIS_PORT', 6379),
        db=env('REDIS_DB', 0),
        password=env('REDIS_PASSWORD', None),
        decode_responses=True
    )

    logging.debug(f"Checking payment status for payment_id: {payment_id}")
    
    try:
        # Проверяем статус платежа через YooKassa API
        payment = Payment.find_one(payment_id)
        logging.debug(f"Payment status: {payment.status}")
        
        if payment.status == "succeeded":
            # Получаем данные платежа из Redis
            payment_data = redis.get(f'payment_{payment_id}')
            
            if payment_data:
                payment_info = json.loads(payment_data)
                tariff_id = payment_info.get('tariff_id')
                user_id = payment_info.get('user_id')
                
                # Создаем подписку
                subscription = db.create_subscription(
                    telegram_id=user_id,
                    tariff_id=tariff_id,
                    payment_id=payment_id,
                    active=True
                )
                
                # Отправляем сообщение об успешной оплате
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="✅ Оплата прошла успешно! Ваша подписка активирована."
                )
                
                # Удаляем данные платежа из Redis
                redis.delete(f'payment_{payment_id}')
                
            else:
                logging.error(f"Payment data not found in Redis for payment_id: {payment_id}")
                context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="Произошла ошибка при проверке платежа. Пожалуйста, обратитесь в поддержку."
                )
        
        elif payment.status == "pending":
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="⏳ Платеж все еще обрабатывается. Пожалуйста, подождите немного и проверьте снова."
            )
        
        else:
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Платеж не прошел. Пожалуйста, попробуйте снова или обратитесь в поддержку."
            )
            
    except Exception as e:
        logging.error(f"Error checking payment status: {e}")
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Произошла ошибка при проверке платежа. Пожалуйста, попробуйте позже."
        )

def activate_subscription(update: Update, context: CallbackContext) -> str:
    """Активирует подписку через YooKassa"""
    
    logging.debug(f"Activating subscription for user {update.effective_user.id}")
    
    # Получаем tariff_id из callback_data
    tariff_id = int(update.callback_query.data.split(':')[1])
    logging.debug(f"Selected tariff_id: {tariff_id}")
    
    # Получаем тариф из базы
    tariff = db.get_tariff(tariff_id)
    logging.debug(f"Got tariff: {tariff.title}")
    
    try:
        # Инициализируем YooKassa
        Configuration.account_id = os.getenv('SHOP_ID')
        Configuration.secret_key = os.getenv('YOOKASSA_TOKEN')
        
        # Создаем платеж
        payment = Payment.create({
            "amount": {
                "value": str(tariff.price),
                "currency": "RUB"
            },
            "confirmation": {
                "type": "redirect",
                "return_url": "https://t.me/Freelincebot"
            },
            "capture": True,
            "description": f"Подписка {tariff.title}",
            "metadata": {
                "tariff_id": tariff_id,
                "user_id": update.effective_user.id
            }
        })
        
        # Инициализируем Redis
        env = Env()
        env.read_env()
        redis = Redis(
            host=env('REDIS_HOST', 'localhost'),
            port=env('REDIS_PORT', 6379),
            db=env('REDIS_DB', 0),
            password=env('REDIS_PASSWORD', None),
            decode_responses=True
        )
        
        # Сохраняем данные платежа в Redis
        payment_data = {
            'tariff_id': tariff_id,
            'user_id': update.effective_user.id,
            'created_at': datetime.now().isoformat()
        }
        redis.setex(
            f'payment_{payment.id}',
            24 * 60 * 60,  # 24 часа
            json.dumps(payment_data)
        )
        logging.debug(f"Set redis keys for payment: {payment.id}")
        
        # Отправляем сообщение с ссылкой на оплату
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"Для оплаты тарифа {tariff.title} перейдите по ссылке:\n{payment.confirmation.confirmation_url}\n\nПосле оплаты нажмите кнопку 'Проверить оплату'",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    "Проверить оплату",
                    callback_data=f"check_payment:{payment.id}"
                )
            ]])
        )
        logging.debug("Payment link sent successfully")
        
        return "SUBSCRIPTION"
        
    except Exception as e:
        logging.error(f"Error sending invoice: {e}")
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Произошла ошибка при создании счета. Пожалуйста, попробуйте позже."
        )
        return "CLIENT"


def confirm_payment(redis: Redis, update: Update, context: CallbackContext) -> None:
    logger.debug('Processing payment confirmation')
    context.bot.answer_pre_checkout_query(
        pre_checkout_query_id=update.pre_checkout_query.id,
        ok=True
    )
    payload = update.pre_checkout_query.invoice_payload
    tariff_id = redis.get(payload)
    logger.debug(f'Got tariff_id from redis: {tariff_id}')
    redis.delete(payload)
    telegram_id = redis.get(f'{payload}_user_id')
    logger.debug(f'Got telegram_id from redis: {telegram_id}')
    redis.delete(f'{payload}_user_id')
    try:
        subscription = db.create_subscription(
            telegram_id=telegram_id,
            tariff_id=tariff_id,
            payment_id=payload
        )
        logger.debug(f'Created subscription: {subscription}')
        send_message_all_managers(
            message=messages.new_subscription_notification(subscription=subscription),
            update=update,
            context=context
        )
        logger.debug('Sent notification to managers')
    except Exception as e:
        logger.error(f'Error creating subscription: {e}')
        context.bot.send_message(
            telegram_id,
            "Произошла ошибка при активации подписки. Пожалуйста, обратитесь в поддержку."
        )


@delete_prev_inline
def edit_service_title(update: Update, context: CallbackContext) -> str:
    """Запрашивает новое название услуги"""
    service_id = int(update.callback_query.data.split(':')[1])
    
    # Сохраняем ID услуги в контексте
    context.user_data['edit_service_id'] = service_id
    
    # Запрашиваем новое название
    context.bot.send_message(
        update.effective_chat.id,
        text="Введите новое название услуги:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Отмена", callback_data="cancel_edit_service")
        ]])
    )
    
    return 'CONTRACTOR_EDIT_SERVICE_TITLE'


@delete_prev_inline
def edit_service_title_input(update: Update, context: CallbackContext) -> str:
    """Сохраняет новое название услуги"""
    service_id = context.user_data.get('edit_service_id')
    
    if not service_id:
        return contractor_services(update, context)
    
    # Получаем новое название
    new_title = update.message.text
    
    # Обновляем услугу
    db.update_service(service_id, title=new_title)
    
    # Отправляем сообщение об успешном обновлении
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.SERVICE_UPDATED_MESSAGE
    )
    
    # Возвращаемся к редактированию услуги
    context.user_data['edit_service_id'] = service_id
    return edit_service(update, context)


@delete_prev_inline
def edit_service_description(update: Update, context: CallbackContext) -> str:
    """Запрашивает новое описание услуги"""
    service_id = int(update.callback_query.data.split(':')[1])
    
    # Сохраняем ID услуги в контексте
    context.user_data['edit_service_id'] = service_id
    
    # Запрашиваем новое описание
    context.bot.send_message(
        update.effective_chat.id,
        text="Введите новое описание услуги:",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Отмена", callback_data="cancel_edit_service")
        ]])
    )
    
    return 'CONTRACTOR_EDIT_SERVICE_DESCRIPTION'


@delete_prev_inline
def edit_service_description_input(update: Update, context: CallbackContext) -> str:
    """Сохраняет новое описание услуги"""
    service_id = context.user_data.get('edit_service_id')
    
    if not service_id:
        return contractor_services(update, context)
    
    # Получаем новое описание
    new_description = update.message.text
    
    # Обновляем услугу
    db.update_service(service_id, description=new_description)
    
    # Отправляем сообщение об успешном обновлении
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.SERVICE_UPDATED_MESSAGE
    )
    
    # Возвращаемся к редактированию услуги
    context.user_data['edit_service_id'] = service_id
    return edit_service(update, context)


@delete_prev_inline
def edit_service_price(update: Update, context: CallbackContext) -> str:
    """Запрашивает новую цену услуги"""
    service_id = int(update.callback_query.data.split(':')[1])
    
    # Сохраняем ID услуги в контексте
    context.user_data['edit_service_id'] = service_id
    
    # Запрашиваем новую цену
    context.bot.send_message(
        update.effective_chat.id,
        text="Введите новую цену услуги (только число):",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("Отмена", callback_data="cancel_edit_service")
        ]])
    )
    
    return 'CONTRACTOR_EDIT_SERVICE_PRICE'


@delete_prev_inline
def edit_service_price_input(update: Update, context: CallbackContext) -> str:
    """Сохраняет новую цену услуги"""
    service_id = context.user_data.get('edit_service_id')
    
    if not service_id:
        return contractor_services(update, context)
    
    try:
        # Пытаемся преобразовать введенный текст в число
        new_price = float(update.message.text)
        
        # Обновляем услугу
        db.update_service(service_id, price=new_price)
        
        # Отправляем сообщение об успешном обновлении
        context.bot.send_message(
            update.effective_chat.id,
            text=messages.SERVICE_UPDATED_MESSAGE
        )
        
        # Возвращаемся к редактированию услуги
        context.user_data['edit_service_id'] = service_id
        return edit_service(update, context)
    
    except ValueError:
        # Если введено не число
        context.bot.send_message(
            update.effective_chat.id,
            text="Пожалуйста, введите корректную цену (только число):",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("Отмена", callback_data="cancel_edit_service")
            ]])
        )
        
        return 'CONTRACTOR_EDIT_SERVICE_PRICE'


@delete_prev_inline
def edit_service_category(update: Update, context: CallbackContext) -> str:
    """Запрашивает новую категорию услуги"""
    service_id = int(update.callback_query.data.split(':')[1])
    
    # Сохраняем ID услуги в контексте
    context.user_data['edit_service_id'] = service_id
    
    # Запрашиваем новую категорию
    context.bot.send_message(
        update.effective_chat.id,
        text="Выберите новую категорию услуги:",
        reply_markup=keyboards.get_categories_keyboard()
    )
    
    return 'CONTRACTOR_EDIT_SERVICE_CATEGORY'


@delete_prev_inline
def edit_service_category_input(update: Update, context: CallbackContext) -> str:
    """Сохраняет новую категорию услуги"""
    service_id = context.user_data.get('edit_service_id')
    
    if not service_id:
        return contractor_services(update, context)
    
    # Получаем ID категории
    category_id = int(update.callback_query.data.split(':')[1])
    
    # Обновляем услугу
    db.update_service(service_id, category_id=category_id)
    
    # Отправляем сообщение об успешном обновлении
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.SERVICE_UPDATED_MESSAGE
    )
    
    # Возвращаемся к редактированию услуги
    context.user_data['edit_service_id'] = service_id
    return edit_service(update, context)


@delete_prev_inline
def edit_service_photo(update: Update, context: CallbackContext) -> str:
    """Запрашивает новое фото услуги"""
    service_id = int(update.callback_query.data.split(':')[1])
    
    # Сохраняем ID услуги в контексте
    context.user_data['edit_service_id'] = service_id
    
    # Запрашиваем новое фото
    context.bot.send_message(
        update.effective_chat.id,
        text="Отправьте новое фото для услуги или нажмите 'Удалить фото', чтобы удалить текущее фото:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Удалить фото", callback_data="delete_service_photo")],
            [InlineKeyboardButton("Отмена", callback_data="cancel_edit_service")]
        ])
    )
    
    return 'CONTRACTOR_EDIT_SERVICE_PHOTO'


@delete_prev_inline
def edit_service_photo_input(update: Update, context: CallbackContext) -> str:
    """Сохраняет новое фото услуги"""
    service_id = context.user_data.get('edit_service_id')
    
    if not service_id or not update.message.photo:
        return contractor_services(update, context)
    
    # Получаем файл с наибольшим разрешением
    photo = update.message.photo[-1]
    file = context.bot.get_file(photo.file_id)
    
    # Создаем директорию для фото, если её нет
    import os
    os.makedirs('media/service_photos', exist_ok=True)
    
    # Генерируем уникальное имя файла
    from uuid import uuid4
    filename = f"service_photos/{uuid4()}.jpg"
    
    # Скачиваем фото
    file.download(f'media/{filename}')
    
    # Обновляем услугу
    db.update_service(service_id, photo=filename)
    
    # Отправляем сообщение об успешном обновлении
    context.bot.send_message(
        update.effective_chat.id,
        text=messages.SERVICE_UPDATED_MESSAGE
    )
    
    # Возвращаемся к редактированию услуги
    context.user_data['edit_service_id'] = service_id
    return edit_service(update, context)


@delete_prev_inline
def delete_service_photo(update: Update, context: CallbackContext) -> str:
    """Удаляет фото услуги"""
    service_id = context.user_data.get('edit_service_id')
    
    if not service_id:
        return contractor_services(update, context)
    
    # Обновляем услугу, устанавливая photo=None
    db.update_service(service_id, photo=None)
    
    # Отправляем сообщение об успешном обновлении
    context.bot.send_message(
        update.effective_chat.id,
        text="Фото услуги успешно удалено!"
    )
    
    # Возвращаемся к редактированию услуги
    context.user_data['edit_service_id'] = service_id
    return edit_service(update, context)


@delete_prev_inline
def cancel_edit_service(update: Update, context: CallbackContext) -> str:
    """Отменяет редактирование услуги"""
    service_id = context.user_data.get('edit_service_id')
    
    if service_id:
        # Возвращаемся к редактированию услуги
        return edit_service(update, context)
    
    # Возвращаемся к списку услуг
    return contractor_services(update, context)


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
                        CallbackQueryHandler(activate_subscription, pattern='activate_subscription'),
                        CallbackQueryHandler(start, pattern=buttons.CANCEL['callback_data']),
                        PreCheckoutQueryHandler(confirm_payment),
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
                        CallbackQueryHandler(add_order_comment, pattern=buttons.ORDER_COMMENT['callback_data']),
                        CallbackQueryHandler(add_order_complaint, pattern=buttons.ORDER_COMPLAINT['callback_data']),
                        CallbackQueryHandler(send_contractor_contact, pattern=buttons.CONTRACTOR_CONTACTS['callback_data']),
                        CallbackQueryHandler(new_contractor, pattern=buttons.NEW_CONTRACTOR['callback_data']),
                        CallbackQueryHandler(client_main, pattern=buttons.CANCEL['callback_data']),
                        CallbackQueryHandler(client_main, pattern=buttons.BACK_TO_CLIENT_MAIN['callback_data']),
                        CallbackQueryHandler(activate_subscription, pattern='activate_subscription'),
                        CallbackQueryHandler(select_category, pattern=buttons.SELECT_CATEGORY['callback_data']),
                        CallbackQueryHandler(show_cart, pattern=buttons.MY_CART['callback_data']),
                    ],
                    'CLIENT_SELECT_CATEGORY': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(show_category_services, pattern=f"^{buttons.CATEGORY_CALLBACK.split(':')[0]}:"),
                        CallbackQueryHandler(client_main, pattern=buttons.CANCEL['callback_data']),
                    ],
                    'CLIENT_BROWSE_SERVICES': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(show_service_details, pattern=f"^{buttons.SERVICE_CALLBACK.split(':')[0]}:"),
                        CallbackQueryHandler(client_main, pattern=buttons.BACK_TO_CLIENT_MAIN['callback_data']),
                        CallbackQueryHandler(show_cart, pattern=buttons.MY_CART['callback_data']),
                    ],
                    'CLIENT_SERVICE_DETAILS': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(add_to_cart, pattern=f"^{buttons.ADD_TO_CART_CALLBACK.split(':')[0]}:"),
                        CallbackQueryHandler(client_main, pattern=buttons.BACK_TO_CLIENT_MAIN['callback_data']),
                        CallbackQueryHandler(show_cart, pattern=buttons.MY_CART['callback_data']),
                    ],
                    'CLIENT_CART': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(remove_from_cart, pattern=f"^{buttons.REMOVE_FROM_CART_CALLBACK.split(':')[0]}:"),
                        CallbackQueryHandler(clear_cart, pattern=buttons.CLEAR_CART['callback_data']),
                        CallbackQueryHandler(checkout, pattern=buttons.CHECKOUT['callback_data']),
                        CallbackQueryHandler(client_main, pattern=buttons.BACK_TO_CLIENT_MAIN['callback_data']),
                    ],
                    'CLIENT_NEW_REQUEST': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.text, callback=client_request_description),
                        CallbackQueryHandler(client_main, pattern=buttons.CANCEL['callback_data']),
                    ],
                    'CLIENT_NEW_COMMENT': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.text, callback=client_comment_description),
                        CallbackQueryHandler(client_main, pattern=buttons.CANCEL['callback_data']),
                    ],
                    'CLIENT_NEW_COMPLAINT': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.text, callback=client_complaint_description),
                        CallbackQueryHandler(client_main, pattern=buttons.CANCEL['callback_data']),
                    ],
                    'CONTRACTOR': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(start, pattern=buttons.CHANGE_ROLE['callback_data']),
                        CallbackQueryHandler(contractor_display_orders, pattern=buttons.CONTRACTOR_AVAILABLE_ORDERS['callback_data']),
                        CallbackQueryHandler(contractor_display_order, pattern=buttons.CURRENT_ORDER['callback_data']),
                        CallbackQueryHandler(contractor_take_order, pattern=buttons.TAKE_ORDER['callback_data']),
                        CallbackQueryHandler(contractor_finish_order, pattern=buttons.FINISH_ORDER['callback_data']),
                        CallbackQueryHandler(contractor_set_estimate_datetime, pattern=buttons.CONTRACTOR_SET_ESTIMATE_DATETIME['callback_data']),
                        CallbackQueryHandler(contractor_display_salary, pattern=buttons.CONTRACTOR_SALARY['callback_data']),
                        CallbackQueryHandler(contractor_main, pattern=buttons.BACK_TO_CONTRACTOR_MAIN['callback_data']),
                        CallbackQueryHandler(contractor_services, pattern=buttons.MY_SERVICES['callback_data']),
                        CallbackQueryHandler(add_service_start, pattern=buttons.ADD_SERVICE['callback_data']),
                        CallbackQueryHandler(edit_service, pattern=f"^{buttons.EDIT_SERVICE_CALLBACK.split(':')[0]}:"),
                        CallbackQueryHandler(delete_service_confirm, pattern=f"^{buttons.DELETE_SERVICE_CALLBACK.split(':')[0]}:"),
                        CallbackQueryHandler(switch_to_client, pattern=buttons.SWITCH_TO_CLIENT['callback_data']),
                    ],
                    'CONTRACTOR_SERVICES': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(add_service_start, pattern=buttons.ADD_SERVICE['callback_data']),
                        CallbackQueryHandler(edit_service, pattern=f"^{buttons.EDIT_SERVICE_CALLBACK.split(':')[0]}:"),
                        CallbackQueryHandler(contractor_main, pattern=buttons.BACK_TO_CONTRACTOR_MAIN['callback_data']),
                    ],
                    'CONTRACTOR_ADD_SERVICE_TITLE': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.text, callback=add_service_title),
                        CallbackQueryHandler(contractor_services, pattern=buttons.CANCEL['callback_data']),
                    ],
                    'CONTRACTOR_ADD_SERVICE_DESCRIPTION': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.text, callback=add_service_description),
                        CallbackQueryHandler(contractor_services, pattern=buttons.CANCEL['callback_data']),
                    ],
                    'CONTRACTOR_ADD_SERVICE_PRICE': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.text, callback=add_service_price),
                        CallbackQueryHandler(contractor_services, pattern=buttons.CANCEL['callback_data']),
                    ],
                    'CONTRACTOR_ADD_SERVICE_CATEGORY': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(add_service_category, pattern=f"^{buttons.CATEGORY_CALLBACK.split(':')[0]}:"),
                        CallbackQueryHandler(contractor_services, pattern=buttons.CANCEL['callback_data']),
                    ],
                    'CONTRACTOR_ADD_SERVICE_PHOTO': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.photo, callback=add_service_photo),
                        CallbackQueryHandler(skip_photo, pattern="skip_photo"),
                        CallbackQueryHandler(contractor_services, pattern=buttons.CANCEL['callback_data']),
                    ],
                    'CONTRACTOR_EDIT_SERVICE': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(contractor_services, pattern=buttons.MY_SERVICES['callback_data']),
                        CallbackQueryHandler(delete_service_confirm, pattern=f"^{buttons.DELETE_SERVICE_CALLBACK.split(':')[0]}:"),
                        CallbackQueryHandler(edit_service_title, pattern=f"^edit_service_title:"),
                        CallbackQueryHandler(edit_service_description, pattern=f"^edit_service_description:"),
                        CallbackQueryHandler(edit_service_price, pattern=f"^edit_service_price:"),
                        CallbackQueryHandler(edit_service_category, pattern=f"^edit_service_category:"),
                        CallbackQueryHandler(edit_service_photo, pattern=f"^edit_service_photo:"),
                        CallbackQueryHandler(cancel_edit_service, pattern="cancel_edit_service"),
                    ],
                    'CONTRACTOR_EDIT_SERVICE_TITLE': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.text, callback=edit_service_title_input),
                        CallbackQueryHandler(cancel_edit_service, pattern="cancel_edit_service"),
                    ],
                    'CONTRACTOR_EDIT_SERVICE_DESCRIPTION': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.text, callback=edit_service_description_input),
                        CallbackQueryHandler(cancel_edit_service, pattern="cancel_edit_service"),
                    ],
                    'CONTRACTOR_EDIT_SERVICE_PRICE': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.text, callback=edit_service_price_input),
                        CallbackQueryHandler(cancel_edit_service, pattern="cancel_edit_service"),
                    ],
                    'CONTRACTOR_EDIT_SERVICE_CATEGORY': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(edit_service_category_input, pattern=f"^{buttons.CATEGORY_CALLBACK.split(':')[0]}:"),
                        CallbackQueryHandler(cancel_edit_service, pattern="cancel_edit_service"),
                    ],
                    'CONTRACTOR_EDIT_SERVICE_PHOTO': [
                        CommandHandler('start', start),
                        MessageHandler(filters=Filters.photo, callback=edit_service_photo_input),
                        CallbackQueryHandler(delete_service_photo, pattern="delete_service_photo"),
                        CallbackQueryHandler(cancel_edit_service, pattern="cancel_edit_service"),
                    ],
                    'CONTRACTOR_DELETE_SERVICE': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(confirm_delete_service, pattern="confirm_delete_service"),
                        CallbackQueryHandler(cancel_delete_service, pattern="cancel_delete_service"),
                    ],
                    'CONTACTOR_SET_ESTIMATE_DATETIME': [
                        CommandHandler('start', start),
                        CallbackQueryHandler(contractor_main, pattern=buttons.BACK_TO_CONTRACTOR_MAIN['callback_data']),
                        MessageHandler(filters=Filters.text, callback=contractor_enter_estimate_datetime),
                    ],
                },
                fallbacks=[],
            )
        )

        updater.dispatcher.add_handler(PreCheckoutQueryHandler(confirm_payment))

        # Добавляем обработчик проверки оплаты
        updater.dispatcher.add_handler(CallbackQueryHandler(
            check_payment_status,
            pattern=r'^check_payment:.*$'
        ))

        updater.start_polling()
        updater.idle()