# coding: utf-8

from django.shortcuts import get_object_or_404, render
from django.contrib.auth.decorators import login_required
from django.http import Http404
from plp.models import CourseSession
from .models import UpsaleLink


@login_required
def op_payment_view(request):
    session_id = request.GET.get('course_session_id', '')
    if not session_id.isdigit():
        raise Http404
    session = get_object_or_404(CourseSession, id=session_id)
    upsale_link_ids = [i for i in request.GET.getlist('upsale_link_ids') if i.isdigit()]
    upsale_links = UpsaleLink.objects.filter(id__in=upsale_link_ids, is_active=True)
    upsales = []
    for upsale in upsale_links:
        s = upsale.content_object
        if s and isinstance(s, CourseSession) and s.id == session.id:
            upsales.append(upsale)
    session_price = session.get_verified_mode_price() or 0
    total_price = session_price + sum([i.get_price() for i in upsales])
    context = {
        'upsale_links': upsales,
        'session': session,
        'total_price': total_price,
    }
    return render(request, 'opro_payments/op_payment.html', context)
