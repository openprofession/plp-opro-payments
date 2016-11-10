# coding: utf-8

from django.conf.urls import url
from . import views

urlpatterns = [
    url(r'^op_payment/?$', views.op_payment_view, name='op_payment'),
    url(r'^op_payment/(?P<session_id>\d+)/(?P<user_id>\d+)/(?P<status>success|fail)/?$',
        views.op_payment_status, name='op_payment_status'),
    url(r'^op_payment/order/(?P<course_session_id>[-\w]+)?$', views.corporate_order_view,
        name='op_payment_corporate_order'),
]
