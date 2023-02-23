from django.http import HttpResponseRedirect
from django.contrib import admin
from django.urls import path
from django.urls import reverse


def redirect2admin(request):
    return HttpResponseRedirect(reverse('admin:index'))

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', redirect2admin),
]
