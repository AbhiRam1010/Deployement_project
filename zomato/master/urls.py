"""
URL configuration for zomato project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from .views import *
urlpatterns = [
    path('masrter_registration',masrter_registration,name='masrter_registration'),
    path('add_item',add_item,name="add_item"),
    path('master_login',master_login,name='master_login'),
    path('user_logout', user_logout, name='user_logout'),
    path('menu',menu,name='menu'),
    path('delete<pk>',delete,name='delete'),
    path('update<pk>',update,name="update"),
    
]+static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)