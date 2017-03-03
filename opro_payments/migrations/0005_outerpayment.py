# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('opro_payments', '0004_auto_20161101_1948'),
    ]

    operations = [
        migrations.CreateModel(
            name='OuterPayment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('data', jsonfield.fields.JSONField(verbose_name='\u0414\u0430\u043d\u043d\u044b\u0435')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='\u0412\u0440\u0435\u043c\u044f \u0441\u043e\u0437\u0434\u0430\u043d\u0438\u044f')),
            ],
            options={
                'verbose_name': '\u0412\u043d\u0435\u0448\u043d\u0438\u0439 \u043f\u043b\u0430\u0442\u0435\u0436',
                'verbose_name_plural': '\u0412\u043d\u0435\u0448\u043d\u0438\u0435 \u043f\u043b\u0430\u0442\u0435\u0436\u0438',
            },
        ),
    ]
