# coding: utf-8

from django.conf import settings
from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from plp.models import CourseSession
from .models import UpsaleLink
from .utils import payment_for_user


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
    total_price = session_price + sum([i.get_price() for i in upsales])

    if request.method == 'POST' and request.is_ajax():
        # действительно создаем платеж только перед отправкой
        payment_for_user(request.user, verified_enrollment, upsales, total_price)
        return JsonResponse({'status': 0})

    payment = payment_for_user(request.user, verified_enrollment, upsales, total_price, create=False)
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
            # TODO
            # "shopFailURL": payment_fail,
            # "shopSuccessURL": payment_success
        },
        'shop_url': settings.YANDEX_MONEY_SHOP_URL,
    }
    return render(request, 'opro_payments/op_payment.html', context)
