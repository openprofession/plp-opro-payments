# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('opro_payments', '0002_upsalelink'),
    ]

    operations = [
        migrations.CreateModel(
            name='ObjectEnrollment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('enrollment_type', models.PositiveSmallIntegerField(verbose_name='\u0422\u0438\u043f \u0437\u0430\u043f\u0438\u0441\u0438', choices=[(0, b'Free'), (1, b'Paid')])),
                ('payment_type', models.PositiveSmallIntegerField(verbose_name='\u0421\u043f\u043e\u0441\u043e\u0431 \u043f\u043b\u0430\u0442\u0435\u0436\u0430', choices=[(0, b'None'), (1, b'Yandex'), (2, b'Other')])),
                ('payment_order_id', models.CharField(max_length=64, null=True, verbose_name='\u041d\u043e\u043c\u0435\u0440 \u0434\u043e\u0433\u043e\u0432\u043e\u0440\u0430/\u0437\u0430\u043a\u0430\u0437\u0430', blank=True)),
                ('payment_descriptions', models.TextField(null=True, verbose_name='\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435 \u043f\u043b\u0430\u0442\u0435\u0436\u0430\\\u0437\u0430\u043a\u0430\u0437\u0430', blank=True)),
                ('is_active', models.BooleanField(verbose_name='\u0421\u0442\u0430\u0442\u0443\u0441 \u0437\u0430\u043f\u0438\u0441\u0438')),
                ('jsonfield', jsonfield.fields.JSONField(null=True, blank=True)),
                ('upsale', models.ForeignKey(related_name='bought_objects', verbose_name='\u0417\u0430\u043f\u0438\u0441\u044c \u043d\u0430 \u043e\u0431\u044a\u0435\u043a\u0442', to='opro_payments.UpsaleLink')),
                ('user', models.ForeignKey(related_name='bought_objects', verbose_name='\u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': '\u0417\u0430\u043f\u0438\u0441\u044c \u043d\u0430 \u043e\u0431\u044a\u0435\u043a\u0442',
                'verbose_name_plural': '\u0417\u0430\u043f\u0438\u0441\u0438 \u043d\u0430 \u043e\u0431\u044a\u0435\u043a\u0442\u044b',
            },
        ),
    ]
