# coding: utf-8

import json
import logging
from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse, HttpResponseServerError, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.core.urlresolvers import reverse
from django.template.loader import get_template
from emails.django import Message
from payments.models import YandexPayment
from plp.models import CourseSession
from plp.notifications.base import get_host_url
from plp_edmodule.models import EducationalModule, EducationalModuleEnrollmentReason
from plp.utils.helpers import get_prefix_and_site
from .forms import CorporatePaymentForm
from .models import UpsaleLink, ObjectEnrollment
from .utils import payment_for_user, client

PAYMENT_SESSION_KEY = 'opro_payment_current_order'


@login_required
def op_payment_view(request):
    """
    Страница подтверждения оплаты сессии или модуля
    """
    session_id = request.GET.get('course_session_id', '')
    module_id = request.GET.get('edmodule_id', '')
    utm_data = request.GET.get('_utm_data', '')
    only_first_course = bool(request.GET.get('only_first_course', False))
    if bool(session_id) == bool(module_id):
        # ожидаем или course_session_id или module_id
        raise Http404
    if (session_id and not session_id.isdigit()) or (module_id and not module_id.isdigit()):
        raise Http404

    obj_model = CourseSession if session_id else EducationalModule
    obj_id = session_id or module_id
    obj = get_object_or_404(obj_model, id=obj_id)
    verified_enrollment = obj.get_verified_mode_enrollment_type()
    if not verified_enrollment:
        raise Http404
    upsale_link_ids = [i for i in request.GET.getlist('upsale_link_ids') if i.isdigit()]
    upsale_links = UpsaleLink.objects.filter(id__in=upsale_link_ids, is_active=True)
    upsales = []
    for upsale in upsale_links:
        s = upsale.content_object
        if s and isinstance(s, obj_model) and s.id == obj.id:
            upsales.append(upsale)

    obj_is_paid = False
    paid_upsales = [i.upsale for i in
                    ObjectEnrollment.objects.filter(upsale__in=upsales, user=request.user).select_related('upsale')]

    first_session_id = None
    session = None
    if session_id:
        if verified_enrollment.is_user_enrolled(request.user):
            obj_is_paid = True
        obj_price = verified_enrollment.price
    else:
        obj_is_paid = EducationalModuleEnrollmentReason.objects.filter(
            enrollment__user=request.user,
            enrollment__module__id=module_id,
            full_paid=not only_first_course
        ).exists()
        if only_first_course:
            try:
                session, price = obj.get_first_session_to_buy(request.user)
                obj_price = price
                first_session_id = session.id
            except TypeError:
                if obj_is_paid:
                    first_session_id = None
                    obj_price = 0
                else:
                    return HttpResponseServerError()
        else:
            obj_price = obj.get_price_list(request.user)['whole_price']

    if obj_is_paid and len(upsales) == len(paid_upsales):
        return HttpResponseRedirect(reverse('frontpage'))

    total_price = 0 if obj_is_paid else obj_price
    total_price += sum([i.get_payment_price() for i in upsales if i not in paid_upsales])

    if request.method == 'POST' and request.is_ajax():
        # действительно создаем платеж только перед отправкой
        try:
            order_number = request.session.get(PAYMENT_SESSION_KEY)
            payment_for_user(request.user, verified_enrollment, set(upsales) - set(paid_upsales), total_price,
                             only_first_course=only_first_course, first_session_id=first_session_id, order_number=order_number)
            del request.session[PAYMENT_SESSION_KEY]
            return JsonResponse({'status': 0})
        except:
            return JsonResponse({'status': 1})

    payment = payment_for_user(request.user, verified_enrollment, set(upsales) - set(paid_upsales), total_price, create=False,
                               only_first_course=only_first_course, first_session_id=first_session_id)
    request.session[PAYMENT_SESSION_KEY] = payment.order_number
    host_url = get_host_url(request)
    payment_fail = host_url + reverse('op_payment_status', kwargs={
        'status': 'fail',
        'obj_id': obj.id,
        'user_id': request.user.id,
        'payment_type': 'session' if session_id else 'edmodule',
    })
    payment_success = host_url + reverse('op_payment_status', kwargs={
        'status': 'success',
        'obj_id': obj.id,
        'user_id': request.user.id,
        'payment_type': 'session' if session_id else 'edmodule',
    })
    if utm_data:
        payment_success = '{}?{}'.format(payment_success, utm_data)

    context = {
        'upsale_links': upsales,
        'total_price': total_price,
        'obj_price': obj_price,
        'obj_is_paid': obj_is_paid,
        'paid_upsales': paid_upsales,
        'object': obj.course if isinstance(obj, CourseSession) else obj,
        'first_session': session,
        'verified': verified_enrollment,
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
    if session_id:
        context['session'] = obj
    else:
        context['module'] = obj
    return render(request, 'opro_payments/op_payment.html', context)


@csrf_exempt
@login_required
def op_payment_status(request, payment_type, obj_id, user_id, status):
    """
    страница payment success/fail, на которую редиректится пользователь после
    оплаты в яндекс кассе
    """
    # не показываем чужие промокоды
    if str(request.user.id) != user_id:
        raise Http404

    template_path = "profile/payment_{}.html".format(status)

    obj_model = CourseSession if payment_type == 'session' else EducationalModule

    obj = get_object_or_404(obj_model, id=obj_id)
    user = request.user

    if payment_type == 'session':
        context = {'session': obj, 'object': obj.course}
    else:
        context = {'module': obj, 'object': obj}

    if status == 'success':
        if payment_type == 'session':
            order_number = "{}-{}-{}-".format('verified', obj.id, user.id)
        else:
            order_number = "edmodule-{}-{}-".format(obj.id, user.id)
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
        if metadata.get('edmodule', {}).get('first_session_id'):
            context['first_session'] = get_object_or_404(CourseSession, id=metadata['edmodule']['first_session_id'])

    return render(request, template_path, context)


def corporate_order_view(request, order_type, obj_id):
    """
    Страница заявки на оплату сессии/модуля юр. лицом
    """
    if order_type == 'session':
        cls = CourseSession
    else:
        cls = EducationalModule
    obj = get_object_or_404(cls, id=obj_id)
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
                'order_type': order_type,
                'object': obj,
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
                'order_type': order_type,
                'object': obj,
            }
            msg.send(context={'context': context, 'request': request})
            return HttpResponseRedirect(reverse('op_payment_corporate_order_done', kwargs={'order_type': order_type}))
    context = {
        'form': form,
        'object': obj.course if order_type == 'session' else obj,
        'order_type': order_type,
    }
    if order_type == 'session':
        context['session'] = obj
    else:
        context['module'] = obj
    return render(request, 'opro_payments/corporate_order.html', context)
