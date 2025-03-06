from django.shortcuts import render
import json
import logging
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from redis import Redis
from main.management.commands.yookassa_webhook import handle_payment_notification

logger = logging.getLogger(__name__)
redis_client = Redis(host='localhost', port=6379, db=0)

# Create your views here.

@csrf_exempt
@require_POST
def yookassa_webhook(request):
    """Обработчик вебхуков от YooKassa"""
    try:
        # Получаем данные уведомления
        notification_data = json.loads(request.body.decode())
        logger.debug(f'Received YooKassa webhook: {notification_data}')
        
        # Обрабатываем уведомление
        handle_payment_notification(notification_data, redis_client)
        
        return HttpResponse(status=200)
        
    except Exception as e:
        logger.error(f'Error processing YooKassa webhook: {e}')
        return HttpResponse(status=500)
