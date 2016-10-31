# coding: utf-8

import json
import logging
from payments.models import YandexPayment


def payment_for_user(user, enrollment_type, upsale_links, price, create=True):
    assert enrollment_type.active == True
    # Яндекс-Касса не даст провести оплату два раза по одному и тому же order_number
    upsales = '-'.join([str(i.id) for i in upsale_links])
    order_number = "{}-{}-{}-{}".format(enrollment_type.mode, enrollment_type.session.id, user.id, upsales)
    if len(order_number) > 64:
        logging.info('Order number exceeds max length: %s' % order_number)
        order_number = order_number[:64]

    metadata = {
        'new_mode': {
            'id': enrollment_type.id,
            'mode': enrollment_type.mode
        },
        'user': {
            'id': user.id,
            'username': user.username
        },
        'upsale_links': [i.id for i in upsale_links],
    }

    try:
        payment = YandexPayment.objects.get(order_number=order_number)
        if payment.order_amount != price:
            assert not payment.is_payed
            logging.warning(
                '[payment_for_user] price changed from %d to %d, updating order_amount for payment %s' %
                (payment.order_amount, price, payment)
            )
            payment.order_amount = price
            payment.save()
    except YandexPayment.DoesNotExist:
        payment_dict = dict(order_number=order_number,
                            order_amount=price,
                            customer_number=user.username,
                            metadata=json.dumps(metadata),
                            user=user)
        if create:
            payment = YandexPayment.objects.create(**payment_dict)
        else:
            payment = YandexPayment(**payment_dict)

    return payment
