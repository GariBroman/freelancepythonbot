from django.http import HttpResponseRedirect
from django.contrib import admin
from django.urls import path
from django.urls import reverse
from main.views import yookassa_webhook


def redirect2admin(request):
    return HttpResponseRedirect(reverse('admin:index'))

urlpatterns = [
    path('admin/', admin.site.urls),
    path('webhook/yookassa/', yookassa_webhook, name='yookassa_webhook'),
]
