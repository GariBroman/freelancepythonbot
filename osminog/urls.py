from django.http import HttpResponseRedirect
from django.contrib import admin
from django.urls import path
from django.urls import reverse
from main.views import yookassa_webhook
from django.conf import settings
from django.conf.urls.static import static


def redirect2admin(request):
    return HttpResponseRedirect(reverse('admin:index'))

urlpatterns = [
    path('admin/', admin.site.urls),
    path('webhook/yookassa/', yookassa_webhook, name='yookassa_webhook'),
]

# Добавляем обработку медиа-файлов в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
