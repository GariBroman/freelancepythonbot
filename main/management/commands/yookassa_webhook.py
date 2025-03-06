import os
import json
import logging
from yookassa import Configuration, Payment
from yookassa.domain.notification import WebhookNotification
from redis import Redis
import main.management.commands.db_processing as db
from telegram import Bot
from telegram.error import TelegramError

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def handle_payment_notification(notification_data: dict, redis: Redis) -> None:
    """Обработка уведомления о платеже от YooKassa"""
    try:
        logger.debug(f'Received payment notification: {notification_data}')
        
        # Инициализация YooKassa
        Configuration.account_id = os.getenv('SHOP_ID')
        Configuration.secret_key = os.getenv('YOOKASSA_TOKEN')
        logger.debug('YooKassa configuration initialized')
        
        # Инициализация бота
        bot = Bot(token=os.getenv('TELEGRAM_BOT_TOKEN'))
        logger.debug('Telegram bot initialized')
        
        # Обработка уведомления
        notification = WebhookNotification(notification_data)
        payment = notification.object
        logger.debug(f'Payment status: {payment.status}')
        
        if payment.status == 'succeeded':
            # Получаем данные из Redis
            payment_data = redis.get(f'payment_{payment.id}')
            logger.debug(f'Payment data from Redis: {payment_data}')
            
            if payment_data:
                payment_info = json.loads(payment_data)
                telegram_id = int(payment_info['telegram_id'])
                tariff_id = payment_info['tariff_id']
                logger.debug(f'Processing payment for user {telegram_id}, tariff {tariff_id}')
                
                # Создаем подписку
                subscription = db.create_subscription(
                    telegram_id=telegram_id,
                    tariff_id=tariff_id,
                    payment_id=payment.id
                )
                logger.debug(f'Created subscription: {subscription}')
                
                # Очищаем данные из Redis
                redis.delete(f'payment_{payment.id}')
                logger.debug(f'Deleted payment data from Redis for payment {payment.id}')
                
                # Отправляем уведомление пользователю
                try:
                    bot.send_message(
                        chat_id=telegram_id,
                        text=f"✅ Оплата прошла успешно!\nПодписка '{subscription.tariff.title}' активирована.\n\nТеперь вы можете отправлять заявки."
                    )
                    logger.debug(f'Sent success notification to user {telegram_id}')
                except TelegramError as e:
                    logger.error(f'Error sending notification to user {telegram_id}: {e}')
                
            else:
                logger.error(f'Payment data not found in Redis for payment_id: {payment.id}')
        else:
            logger.debug(f'Payment {payment.id} status is not succeeded: {payment.status}')
        
    except Exception as e:
        logger.error(f'Error handling payment notification: {e}')
        raise 