# coding: utf-8

import json
import hmac
import logging
import re
import traceback

from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser
from django.http import Http404, JsonResponse, HttpResponseServerError, HttpResponseRedirect, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.urlresolvers import reverse
from django.core.validators import validate_email
from django.template.loader import get_template
from django.utils.crypto import constant_time_compare
from django.utils.translation import ugettext as _

import requests
from decimal import Decimal

from emails.django import Message
from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from payments.models import YandexPayment
from plp.models import CourseSession, User, Course, EnrollmentReason, GiftPaymentInfo
from plp.notifications.base import get_host_url
from plp_edmodule.models import EducationalModule, EducationalModuleEnrollmentReason, PromoCode
from plp.utils.helpers import get_prefix_and_site
from .forms import CorporatePaymentForm, GiftForm
from .models import UpsaleLink, ObjectEnrollment, OuterPayment
from .utils import increase_promocode_usage, get_merchant_receipt, payment_for_user, client, outer_payment_for_user, get_or_create_user, get_payment_urls, get_gift_payment_urls, get_object_info, get_obj_price

PAYMENT_SESSION_KEY = 'opro_payment_current_order'

def apply_promocode(promocode, product_id, product_type, session_id, only_first_course, request=None):
    try:
        obj = PromoCode.objects.get(code=promocode)
    except ObjectDoesNotExist:
        return {
            'status': 1,
            'message': _(u'Промокод не найден')
        }

    validation_result = obj.validate(int(product_id), product_type)
    if validation_result['status'] != 0:
        return validation_result

    calculations = obj.calculate(product_id=product_id, session_id=session_id, only_first_course=only_first_course)
    if request:
        request.session['promocode'] = {
            'code': promocode,
            'new_price' : "%.2f" % calculations['new_price'].quantize(Decimal('.00'))
        }
    return calculations

    return {
        'status': 1,
        'response': _(u'Что-то пошло не так')
    }

def promocode(request):
    if request.method == 'POST' and request.is_ajax():
        promocode = request.POST.get('promocode', '').strip()
        product_id = request.POST.get('product_id', '').strip()
        product_type = request.POST.get('product_type', '').strip()
        session_id = request.POST.get('session_id', '').strip()
        only_first_course = True if request.POST.get('only_first_course', '').strip().lower() == 'true' else False

        result = apply_promocode(promocode, product_id, product_type, session_id, only_first_course, request=request)
        
        return JsonResponse(result)

    else:
        raise Http404

def landing_op_payment_view(request):
    """
    Страница подтверждения оплаты сессии или модуля при переходе с лэндинга
    """

    first_name = request.GET.get('first_name', '')
    email = request.GET.get('email', '')
    phone = request.GET.get('phone', '')
    session_id = request.GET.get('course_session_id', '')
    module_id = request.GET.get('edmodule_id', '')
    utm_data = request.GET.get('_utm_data', '')
    only_first_course = bool(request.GET.get('only_first_course', False))
    promocode = request.GET.get('promocode', '')
    contented = True if request.GET.get('contented', '') == 'true' else False

    if bool(session_id) == bool(module_id):
        raise Http404
    if (session_id and not session_id.isdigit()) or (module_id and not module_id.isdigit()):
        raise Http404

    payment_fields =  {
        "shopId": settings.YANDEX_MONEY_SHOP_ID,
        "scid": settings.YANDEX_MONEY_SCID,
        "orderNumber": "",
        "customerNumber": "",
        "sum": "",
        "cps_email": "",
        "cps_phone": "",
        "shopFailURL": "",
        "shopSuccessURL": "",
        "ym_merchant_receipt":""
    }

    """
    Сценарий, при котором данные о пользователе приходят с лэндинга
    Необходимо максимально быстро отдать страницу пользователю, чтобы в фоновом режиме
    подготовить необходимые для платежа данные и сделать редирект на Яндекс.Кассы
    """

    with_landing_user = False
    if request.method == 'GET' and first_name and email:
        try:
            validate_email(email)
        except:
            raise Http404
        with_landing_user = True

    if with_landing_user:
        context = {
            'landing': True,
            'contented': contented,
            'with_landing_user': with_landing_user,
            'fields': payment_fields,
            'shop_url': settings.YANDEX_MONEY_SHOP_URL,
        }

        return render(request, 'opro_payments/landing_op_payment.html', context)

    # Сценарий оплаты с регистрацией пользователя с лэндинга
    if request.method == 'POST' and request.is_ajax() and request.POST.get('with_landing_user', ''):
        try:
            if promocode: 
                result = apply_promocode(promocode, module_id, 'edmodule' if module_id else 'course', session_id, only_first_course)
                if result['status'] == 0:
                    new_price = result['new_price']
                    promocode_message = None
                elif result['status'] != 0:
                    new_price = None
                    promocode_message = result['message']
            else:
                new_price = None
                promocode_message = None

            obj, verified_enrollment, upsales = get_object_info(request, session_id, module_id)

            if not verified_enrollment:
                raise Http404
                
            session, first_session_id, obj_price, total_price, products = get_obj_price(session_id, verified_enrollment, only_first_course, obj, upsales, new_price)
            user = get_or_create_user(first_name, email, phone=phone)
            payment_urls = get_payment_urls(request, obj, user, session_id, utm_data) 
            payment = payment_for_user(request, verified_enrollment, set(upsales), total_price,
                                user=user, only_first_course=only_first_course, first_session_id=first_session_id, promocode=promocode)

            return JsonResponse({
                'status': 0,
                'orderNumber': payment.order_number,
                'customerNumber': payment.customer_number,
                'sum': payment.order_amount,
                'cps_email': user.email,
                'shopFailURL': payment_urls['payment_fail'],
                'shopSuccessURL': payment_urls['payment_success'],
                'promocode_message': promocode_message,
                'ym_merchant_receipt': get_merchant_receipt(user.email, products)
            })
        except Exception as e:
            return JsonResponse({
                'status': 1,
                'traceback': str(traceback.format_exc())
                })

    """
    Сценарий, когда имя и email пользователь вводи на странице OpenProfession
    """

    obj, verified_enrollment, upsales = get_object_info(request, session_id, module_id)

    if not verified_enrollment:
        raise Http404

    session, first_session_id, obj_price, total_price, products = get_obj_price(session_id, verified_enrollment, only_first_course, obj, upsales)

    # Сценарий оплаты с регистрацией пользователя с сайта OpenProfession
    if request.method == 'POST' and request.is_ajax():
        try:
            if 'promocode' in request.session:
                new_price = Decimal(request.session['promocode']['new_price'])
                session, first_session_id, obj_price, total_price, products = get_obj_price(
                                                                                        session_id, 
                                                                                        verified_enrollment, 
                                                                                        only_first_course, 
                                                                                        obj, 
                                                                                        upsales, 
                                                                                        new_price
                                                                                    )

            user = get_or_create_user(request.POST.get('firstname', ''), request.POST.get('email', ''))
            payment_urls = get_payment_urls(request, obj, user, session_id, utm_data) 
            
            payment = payment_for_user(request, verified_enrollment, set(upsales), total_price,
                             user=user, only_first_course=only_first_course, first_session_id=first_session_id, 
                             promocode=request.session.get('promocode', {}).get('code', None))

            if 'promocode' in request.session:
                del request.session['promocode']

            return JsonResponse({
                'status': 0,
                'orderNumber': payment.order_number,
                'customerNumber': payment.customer_number,
                'sum': payment.order_amount,
                'cps_email': user.email,
                'shopFailURL': payment_urls['payment_fail'],
                'shopSuccessURL': payment_urls['payment_success'],
                'ym_merchant_receipt': get_merchant_receipt(user.email, products)
            })
        except Exception as e:
            return JsonResponse({
                'status': 1,
                'traceback': str(traceback.format_exc())
                })

    context = {
        'upsale_links': upsales,
        'total_price': total_price,
        'obj_price': obj_price,
        'object': obj.course if isinstance(obj, CourseSession) else obj,
        'first_session': session,
        'verified': verified_enrollment,
        'landing': True,
        'contented': contented,
        'with_landing_user': with_landing_user,
        'fields': payment_fields,
        'shop_url': settings.YANDEX_MONEY_SHOP_URL,
        'only_first_course': only_first_course,
    }
    if session_id:
        context['session'] = obj
    else:
        context['module'] = obj
    return render(request, 'opro_payments/landing_op_payment.html', context)

def landing_op_payment_status(request, payment_type, obj_id, user_id, status):
    """
    страница payment success/fail, на которую редиректится пользователь после
    оплаты в яндекс кассе с лэндинга
    """

    template_path = "profile/payment_{}.html".format(status)

    obj_model = CourseSession if payment_type == 'session' else EducationalModule

    obj = get_object_or_404(obj_model, id=obj_id)
    user = get_object_or_404(User, id=user_id)

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
        
        increase_promocode_usage(metadata.get('promocode', None), payment.id)

        context['landing'] = True
        context['landing_username'] = user.first_name

    return render(request, template_path, context)  

def gift_op_payment_view(request):

    session_id = request.GET.get('course_session_id', '')
    module_id = request.GET.get('edmodule_id', '')
    utm_data = request.GET.get('_utm_data', '')
    only_first_course = bool(request.GET.get('only_first_course', False))

    product = request.GET.get('product')
    if not (product == 'ux' or product == 'vr'):
        raise Http404

    if bool(session_id) == bool(module_id):
        raise Http404
    if (session_id and not session_id.isdigit()) or (module_id and not module_id.isdigit()):
        raise Http404

    payment_fields =  {
        "shopId": settings.YANDEX_MONEY_SHOP_ID,
        "scid": settings.YANDEX_MONEY_SCID,
        "orderNumber": "",
        "customerNumber": "",
        "sum": "",
        "cps_email": "",
        "cps_phone": "",
        "shopFailURL": "",
        "shopSuccessURL": "",
        "ym_merchant_receipt":""
    }

    obj, verified_enrollment, upsales = get_object_info(request, session_id, module_id)

    if not verified_enrollment:
        raise Http404

    if request.method == 'POST' and request.is_ajax():
        try:
            gift_form = GiftForm(request.POST)
            if gift_form.is_valid():
                session, first_session_id, obj_price, total_price, products = get_obj_price(session_id, verified_enrollment, only_first_course, obj, upsales)
                gift_sender = get_or_create_user(gift_form.cleaned_data['gift_sender'], gift_form.cleaned_data['gift_sender_email'])
                gift_receiver = get_or_create_user(gift_form.cleaned_data['gift_receiver'], gift_form.cleaned_data['gift_receiver_email'], lazy_send_mail=True)
                payment_urls = get_gift_payment_urls(request, obj, gift_sender, session_id, utm_data)             
                payment = payment_for_user(request, verified_enrollment, set(upsales), total_price,
                                user=gift_sender, 
                                only_first_course=only_first_course, 
                                first_session_id=first_session_id,
                                gift_receiver=gift_receiver)

                gift_payment_info = GiftPaymentInfo(
                    course_id=session_id,
                    gift_receiver=gift_receiver,
                    gift_sender=gift_sender,
                    has_paid=False,
                    has_notified=False,
                    notification_date=gift_form.cleaned_data['send_date'],
                    gift_text=gift_form.cleaned_data['mail_template'],
                    product=product
                )

                gift_payment_info.save()

                return JsonResponse({
                    'status': 0,
                    'orderNumber': payment.order_number,
                    'customerNumber': payment.customer_number,
                    'sum': payment.order_amount,
                    'cps_email': gift_sender.email,
                    'shopFailURL': payment_urls['payment_fail'],
                    'shopSuccessURL': payment_urls['payment_success'],
                    'ym_merchant_receipt': get_merchant_receipt(gift_sender.email, products)
                })
            else:
                return HttpResponseBadRequest()
        except Exception as e:
            import traceback
            return JsonResponse({
                'status': 1,
                'traceback': str(traceback.format_exc())
                })

    context = {
        'form': GiftForm(),
        'fields': payment_fields,
        'product': product,
        'shop_url': settings.YANDEX_MONEY_SHOP_URL,
    }

    return render(request, 'opro_payments/gift_op_payment.html', context)

def gift_op_payment_status(request, payment_type, obj_id, user_id, status):
    """
    страница payment success/fail, на которую редиректится пользователь после
    оплаты в яндекс кассе с лэндинга
    """

    template_path = "profile/gift_payment_{}.html".format(status)

    obj_model = CourseSession if payment_type == 'session' else EducationalModule

    obj = get_object_or_404(obj_model, id=obj_id)
    user = get_object_or_404(User, id=user_id)

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

        promocode = metadata.get('promocode', None)
        if promocode:
            try:
                promocode_object = PromoCode.objects.get(code=promocode)
                promocode_object.used += 1
                promocode_object.save()
            except ObjectDoesNotExist:
                logging.error('Promocode %s wasn\'t found for payment %s' % (
                    promocode, payment.id
                ))

        context['landing'] = True
        context['landing_username'] = user.first_name

    return render(request, template_path, context)

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
    products = []
    if session_id:
        if verified_enrollment.is_user_enrolled(request.user):
            obj_is_paid = True
        obj_price = verified_enrollment.price
        if not obj_is_paid:
            products.append({ 
                'title': verified_enrollment.session.course.title, 
                'price': obj_price 
            })
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
                products.append({
                    'title': session.course.title,
                    'price': obj_price 
                })
            except TypeError:
                if obj_is_paid:
                    first_session_id = None
                    obj_price = 0
                else:
                    return HttpResponseServerError()
        else:
            obj_price = obj.get_price_list(request.user)['whole_price']
            products.append({
                'title': obj.title, 
                'price': obj_price 
            })

    if obj_is_paid and len(upsales) == len(paid_upsales):
        return HttpResponseRedirect(reverse('frontpage'))

    total_price = 0 if obj_is_paid else obj_price

    upsales_price = 0
    for i in upsales:
        if i not in paid_upsales:
            upsale_price = i.get_payment_price()
            upsales_price += upsale_price
            products.append({
                'title': i.upsale.title,
                'price': upsale_price
            })

    total_price += upsales_price

    if request.method == 'POST' and request.is_ajax():
        # действительно создаем платеж только перед отправкой
        try:
            if 'promocode' in request.session:
                new_price = Decimal(request.session['promocode']['new_price'])
                total_price = 0 if obj_is_paid else float(new_price)
                total_price += upsales_price

            order_number = request.session.get(PAYMENT_SESSION_KEY)
            payment_for_user(request, verified_enrollment, set(upsales) - set(paid_upsales), total_price,
                             only_first_course=only_first_course, first_session_id=first_session_id, order_number=order_number, promocode=request.session.get('promocode', {}).get('code', None))
            
            if 'promocode' in request.session:
                del request.session['promocode']

            del request.session[PAYMENT_SESSION_KEY]
            
            return JsonResponse({'status': 0})
        except:
            return JsonResponse({
                'status': 1,
                'traceback': str(traceback.format_exc())
                })

    payment = payment_for_user(request, verified_enrollment, set(upsales) - set(paid_upsales), total_price, create=False,
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
            "shopSuccessURL": payment_success,
            "ym_merchant_receipt": json.dumps(get_merchant_receipt(request.user.email, products), ensure_ascii=False)
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

        increase_promocode_usage(metadata.get('promocode', None), payment.id)

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


class EnrollmentApiViewException(Exception):
    pass


class EnrollmentApiPermission(permissions.BasePermission):
    """
    Проверка подлинности запроса оплаты по лендингу:
    """
    def has_permission(self, request, view):
        secret_key = settings.LANDING_ECOMMERCE_SECRET
        key = request.META.get('HTTP_X_WC_WEBHOOK_SIGNATURE') or ''
        body = request.stream.body
        return constant_time_compare(hmac.new(secret_key, body).hexdigest(), key)


class EnrollmentApiView(APIView):
    """
    view обработки записи на курсы/специализации с лендинга.
    """
    DEBUG_EMAIL_TO = getattr(settings, 'ENROLLMENT_API_DEBUG_EMAIL', 'debug@openprofession.ru')
    permission_classes = (EnrollmentApiPermission, )

    def post(self, request):
        outer_payment = OuterPayment.objects.create(data=request.data)
        sku, email = '', ''
        warnings = []
        new_user_created = False
        # при возникновении исключений EnrollmentApiViewException на этом шаге запись на
        # курс/специализацию/апсейл не происходит
        try:
            email = request.data.get('order', {}).get('customer', {}).get('email')
            if not email:
                raise EnrollmentApiViewException(u'Данные не содержат email')
            sku = request.data.get('order', {}).get('line_items', [])
            if len(sku) != 1:
                raise EnrollmentApiViewException(_(u'Ожидается 1 элемент в line_items, пришло %s') % len(sku))
            elif not sku[0].get('sku'):
                raise EnrollmentApiViewException(u'Данные не содержат sku')
            # разделитель +
            sku = sku[0]['sku']
            sku_parts = self.parse_sku(sku)
            try:
                validate_email(email)
            except ValidationError:
                raise EnrollmentApiViewException(u'Задан невалидный емейл %s' % email)
            user = User.objects.filter(email=email).first()
            obj, upsales, log = self.items_to_buy(sku_parts, user)
            warnings.extend(log)
            if not user:
                user = self.create_user(email)
                new_user_created = True
        except EnrollmentApiViewException as e:
            logging.error(u'outer payment %s error: %s' % (outer_payment.id, e))
            if client:
                client.captureMessage('outer payment error', extra={
                    'exception': u'%s' % e,
                    'request_data': request.data,
                })
            self.send_debug_mail(error=u'%s' % e, sku=sku, email=email, outer_payment=outer_payment)
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # далее записываем пользователя на те объекты из sku, на которые он не был записан
        if not new_user_created:
            warnings.extend(self.check_items_for_user(user, sku_parts, obj, upsales))
        new_mode = obj.get_verified_mode_enrollment_type()
        mode_data = {'id': new_mode.id, 'mode': new_mode.mode}
        if sku_parts['type'] == 'edmodule':
            mode_data['only_first_course'] = sku_parts['only_first_course']
            if sku_parts['only_first_course']:
                mode_data['first_session_id'] = sku_parts['first_session_id']
        outer_payment_for_user(user, sku_parts, mode_data, upsales)
        self.send_debug_mail(warnings=warnings, sku=sku, email=email, outer_payment=outer_payment)
        return Response(status=status.HTTP_200_OK)

    def send_debug_mail(self, **kwargs):
        msg = Message(
            subject=get_template('opro_payments/emails/outer_payment_debug_subject.txt'),
            html=get_template('opro_payments/emails/outer_payment_debug_message.html'),
            mail_from=settings.EMAIL_NOTIFICATIONS_FROM,
            mail_to=self.DEBUG_EMAIL_TO
        )
        try:
            msg.send(context={'context': kwargs, 'request': self.request})
        except Exception as e:
            logging.error('Failed to send outer payment debug email: %s' % e)
            if client:
                client.captureMessage('Failed to send outer payment debug email', extra={
                    'exception': str(e),
                    'email_context': kwargs,
                })

    def create_user(self, email):
        post_data = {'emails': [email]}
        request_url = '{}/users/simple_mass_registration/'.format(settings.SSO_NPOED_URL)
        try:
            logging.info('Request %s with data=%s' % (request_url, post_data))
            r = requests.post(
                request_url,
                json=post_data,
                headers={'X-SSO-Api-Key': settings.SSO_API_KEY},
                timeout=settings.CONNECTION_TIMEOUT
            )
            assert r.status_code == 200, 'SSO status code %s' % r.status_code
            sso_data = r.json().get('users', [])
            assert len(sso_data) == 1 and 'username' in sso_data[0], 'SSO returned %s' % sso_data
            return User.objects.get(username=sso_data[0]['username'])
        except (requests.RequestException, AssertionError, ValueError, User.DoesNotExist) as exc:
            error_dict = {'data': post_data, 'exception': str(exc)}
            if client:
                client.captureMessage('error creating user', extra=error_dict)
            logging.error('error creating user: data={data}, exception: {exception}'.format(**error_dict))
            raise EnrollmentApiViewException(u'Не удалось создать пользователя %s: %s' % (email, str(exc)))

    def parse_sku(self, sku):
        parts = sku.split('+')
        result = {}
        if len(parts) < 3:
            raise EnrollmentApiViewException(
                u'Получен некорректный sku %s, sku должен состоять как минимум из 3 частей' % sku)
        if parts[0] == 'course':
            result.update({
                'type': 'course',
                'slug': parts[2],
                'uni_slug': parts[1],
            })
        elif parts[0] == 'edmodule':
            if parts[2] not in ['all', 'one']:
                raise EnrollmentApiViewException(
                    u'Получен некорректный sku %s, 3 часть sku при записи на специализацию должна быть all или one'
                    % sku)
            only_first_course = parts[2] == 'one'
            result.update({
                'type': 'edmodule',
                'slug': parts[1],
                'only_first_course': only_first_course,
            })
        else:
            raise EnrollmentApiViewException(
                u'Получен некорректный sku %s, 1 часть sku должна быть course или edmodule' % sku)
        upsale_ids = []
        for p in parts[3:]:
            upsale_id = re.match(r'^upsalelink(\d+)$', p)
            if not upsale_id:
                raise EnrollmentApiViewException(u'Получен некорректный sku %s, не удалось распарсить апсейлы' % sku)
            upsale_ids.append(int(upsale_id.group(1)))
        result['upsales'] = upsale_ids
        return result

    def check_items_for_user(self, user, sku_parts, obj, upsales):
        """
        проверка наличия у пользователя уже оплаченных курсов/апсейлов/специализаций
        """
        log = []
        if sku_parts['type'] == 'course':
            has_paid = EnrollmentReason.objects.filter(
                participant__user=user,
                participant__session=obj,
                session_enrollment_type__mode='verified'
            ).exists()
            if has_paid:
                log.append(_(u'Пользователь %s уже оплачивал курс %s') % (user.email, obj.get_absolute_slug_v1()))
                logging.error('EnrollmentApiView: user %s already paid for course %s' %
                              (user, obj.get_absolute_slug_v1()))
        elif sku_parts['type'] == 'edmodule':
            has_paid = obj.get_enrollment_reason_for_user(user)
            if has_paid:
                log.append(_(u'Пользователь %s уже оплачивал специализацию %s') % (user.email, obj.code))
                logging.error('EnrollmentApiView: user %s already paid for edmodule %s' % (user, obj.code))

        paid_upsales = ObjectEnrollment.objects.filter(
            user=user,
            upsale__id__in=upsales
        ).values_list('upsale_id', flat=True)
        if paid_upsales:
            log.append(_(u'Пользователь уже оплачивал апсейл(ы): %s') %
                       ', '.join(map(lambda x: str(x), paid_upsales)))
            logging.error('EnrollmentApiView: user %s already paid for upsales %s'
                          % (user, ', '.join(map(lambda x: str(x), paid_upsales))))
        return log

    def items_to_buy(self, sku, user):
        """
        выбор объектов для покупки
        """
        if sku['type'] == 'course':
            try:
                course = Course.objects.get(slug=sku['slug'], university__slug=sku['uni_slug'])
                obj = course.next_session
            except Course.DoesNotExist:
                raise EnrollmentApiViewException(u'курс %(uni_slug)s+%(slug)s не найден' % sku)
            else:
                if not obj:
                    raise EnrollmentApiViewException(u'курс %s не имеет открытых сессий' % course)
                if not obj.get_verified_mode_enrollment_type():
                    raise EnrollmentApiViewException(u'у сессии %s нет платного варианта записи' % obj)
                if obj.allow_enrollments():
                    raise EnrollmentApiViewException(u'сессия %s не доступна для записи' % obj)
        else:
            try:
                obj = EducationalModule.objects.get(code=sku['slug'])
            except EducationalModule.DoesNotExist:
                raise EnrollmentApiViewException(u'модуль %(slug)s не найден' % sku)
            if not obj.get_verified_mode_enrollment_type():
                raise EnrollmentApiViewException(u'у модуля %s нет платного варианта записи' % obj)
            if sku['only_first_course']:
                if not user:
                    user = AnonymousUser()
                else:
                    reason = obj.get_enrollment_reason_for_user(user)
                    if reason:
                        if reason.full_paid:
                            msg = _(u'Пользователь %s уже оплачивал полностью специализацию %s') % \
                                (user.email, obj.code)
                        else:
                            msg = _(u'Пользователь %s уже оплачивал частично специализацию %s') % \
                                (user.email, obj.code)
                        raise EnrollmentApiViewException(msg)
                first_session = obj.get_first_session_to_buy(user)
                if not first_session:
                    if user.is_authenticated():
                        raise EnrollmentApiViewException(
                            _(u'не удалось выбрать курс для частичной оплаты специализации %s для пользователя %s') %
                            (obj.code, user.username)
                        )
                    else:
                        raise EnrollmentApiViewException(
                            _(u'не удалось выбрать курс для частичной оплаты специализации %s') %
                            obj.code
                        )
                sku['first_session_id'] = first_session[0].id
        upsales = UpsaleLink.objects.filter(id__in=sku['upsales'])
        log, available_upsales = [], []
        for u in upsales:
            if not u.is_active:
                log.append(_(u'Аспейл #%s не активен') % u.id)
            elif u.content_object != obj:
                log.append(_(u'Аспейл #%s не относится к выбранному объекту %s') % (u.id, obj))
            else:
                available_upsales.append(u.id)
        not_found_upsales = set([long(i) for i in sku['upsales']]) - set([i.id for i in upsales])
        if not_found_upsales:
            log.append(_(u'Апсейлы со следующими id не найдены: %s') %
                       ', '.join(map(lambda x: str(x), not_found_upsales)))
        return obj, available_upsales, log
