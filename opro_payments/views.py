# coding: utf-8

import json
import logging
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.template.loader import get_template
from emails.django import Message
from payments.models import YandexPayment
from plp.models import CourseSession
from plp.notifications.base import get_host_url
from plp.utils.helpers import get_prefix_and_site
from .forms import CorporatePaymentForm
from .models import UpsaleLink, ObjectEnrollment
from .utils import payment_for_user, client


@login_required
def op_payment_view(request):
    session_id = request.GET.get('course_session_id', '')
    if not session_id.isdigit():
        raise Http404
    session = get_object_or_404(CourseSession, id=session_id)
    verified_enrollment = session.get_verified_mode_enrollment_type()
    if not verified_enrollment:
        raise Http404
    upsale_link_ids = [i for i in request.GET.getlist('upsale_link_ids') if i.isdigit()]
    upsale_links = UpsaleLink.objects.filter(id__in=upsale_link_ids, is_active=True)
    upsales = []
    for upsale in upsale_links:
        s = upsale.content_object
        if s and isinstance(s, CourseSession) and s.id == session.id:
            upsales.append(upsale)
    session_price = verified_enrollment.price
    total_price = session_price + sum([i.get_payment_price() for i in upsales])

    if request.method == 'POST' and request.is_ajax():
        # действительно создаем платеж только перед отправкой
        payment_for_user(request.user, verified_enrollment, upsales, total_price)
        return JsonResponse({'status': 0})

    payment = payment_for_user(request.user, verified_enrollment, upsales, total_price, create=False)
    host_url = get_host_url(request)
    payment_fail = host_url + reverse('op_payment_status', kwargs={
        'status': 'fail',
        'session_id': session.id,
        'user_id': request.user.id,
    })
    payment_success = host_url + reverse('op_payment_status', kwargs={
        'status': 'success',
        'session_id': session.id,
        'user_id': request.user.id,
    })

    context = {
        'upsale_links': upsales,
        'session': session,
        'total_price': total_price,
        'fields': {
            "shopId": settings.YANDEX_MONEY_SHOP_ID,
            "scid": settings.YANDEX_MONEY_SCID,
            "orderNumber": payment.order_number,
            "customerNumber": payment.customer_number,
            "sum": payment.order_amount,
            "cps_email": request.user.email,
            "cps_phone": "",
            "shopFailURL": payment_fail,
            "shopSuccessURL": payment_success
        },
        'shop_url': settings.YANDEX_MONEY_SHOP_URL,
    }
    return render(request, 'opro_payments/op_payment.html', context)


@csrf_exempt
@login_required
def op_payment_status(request, session_id, user_id, status):
    # не показываем чужие промокоды
    if str(request.user.id) != user_id:
        raise Http404

    template_path = "profile/payment_{}.html".format(status)

    session = get_object_or_404(CourseSession, id=session_id)
    user = request.user

    context = {
        'session': session,
    }

    if status == 'success':
        order_number = "{}-{}-{}-".format('verified', session.id, user.id)
        # считаем, что к моменту перехода на страницу подтверждения оплаты, нам пришел ответ от Яндекса
        # и были созданы "записи на объекты", иначе пользователь не увидит промокоды
        payment = YandexPayment.objects.filter(order_number__startswith=order_number).order_by('-id').first()
        if not payment:
            raise Http404
        if not payment.is_payed:
            logging.error('User %s was redirected to successfull payment page before payment %s was processed' % (
                user.id, payment.id
            ))
            if client:
                client.captureMessage('User was redirected to successfull payment page before payment was processed',
                                      extra={'user_id': user.id, 'payment_id': payment.id})
        metadata = json.loads(payment.metadata or '{}')
        upsale_links = metadata.get('upsale_links', [])
        upsales = UpsaleLink.objects.filter(id__in=upsale_links)
        object_enrollments = ObjectEnrollment.objects.filter(user=user, upsale__id__in=upsale_links)
        promocodes = []
        for obj in object_enrollments:
            data = obj.jsonfield or {}
            promo = data.get('promo_code')
            if promo:
                promocodes.append((obj.upsale.upsale.title, promo))
        context.update({
            'promocodes': promocodes,
            'upsale_links': upsales,
            'shop_url': getattr(settings, 'OPRO_PAYMENT_SHOP_URL', ''),
        })

    return render(request, template_path, context)


def corporate_order_view(request, course_session_id):
    session = get_object_or_404(CourseSession, id=course_session_id)
    form = CorporatePaymentForm(request.POST or None)
    if request.method == 'POST':
        if form.is_valid():
            email = getattr(settings, 'OPRO_PAYMENTS_CORPORATE_ORDER_EMAIL', 'Partners@openprofession.ru')
            msg = Message(
                subject=get_template('opro_payments/emails/corporate_order_email_subject.txt'),
                html=get_template('opro_payments/emails/corporate_order_email_html.html'),
                mail_from=settings.EMAIL_NOTIFICATIONS_FROM,
                mail_to=form.cleaned_data['email'],
                headers={'Reply-To': email}
            )
            context = {
                'user': request.user if request.user.is_authenticated() else None,
                'session': session,
            }
            context.update(get_prefix_and_site())
            msg.send(context={'context': context, 'request': request})

            msg = Message(
                subject=get_template('opro_payments/emails/corporate_order_ticket_subject.txt'),
                html=get_template('opro_payments/emails/corporate_order_ticket_message.html'),
                mail_from=settings.EMAIL_NOTIFICATIONS_FROM,
                mail_to=email
            )
            context = {
                'form': form,
                'session': session
            }
            msg.send(context={'context': context, 'request': request})
            # TODO: thank you page
            # return HttpResponseRedirect(reverse(''))
            return HttpResponseRedirect(reverse('op_payment_corporate_order', kwargs={'course_session_id': course_session_id}))
    context = {
        'form': form,
        'session': session,
        'object': session.course,
    }
    return render(request, 'opro_payments/corporate_order.html', context)
