from django.contrib import admin
from django.urls import path
from django.conf.urls.static import static
from django.conf import settings
from .views import *

urlpatterns = [
path('user_regitration/',user_regitration,name='user_regitration'),
path('user_login',user_login,name='user_login'),
path('user_logout',user_logout,name='user_logout'),
path('go_to_menu',go_to_menu,name='go_to_menu'),
path('add_cart<pk>',add_cart,name='add_cart'),
path('cart',cart,name='cart'),
path('Buy',Buy,name='Buy'),

]+static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)