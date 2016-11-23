# coding: utf-8

from django.conf.urls import url
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    url(r'^op_payment/?$', views.op_payment_view, name='op_payment'),
    url(r'^op_payment/(?P<payment_type>session|edmodule)/(?P<obj_id>\d+)/(?P<user_id>\d+)/(?P<status>success|fail)/?$',
        views.op_payment_status, name='op_payment_status'),
    url(r'^op_payment/order/(?P<course_session_id>\d+)/?$', views.corporate_order_view,
        name='op_payment_corporate_order'),
    url(r'op_payment/order/thank-you/?$', TemplateView.as_view(template_name='opro_payments/thank_you_page.html'),
        name='op_payment_corporate_order_done'),
]
