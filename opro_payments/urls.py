# coding: utf-8

from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^op_payment/?$', views.op_payment_view, name='op_payment'),
]
