# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('opro_payments', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='UpsaleLink',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('object_id', models.PositiveIntegerField(verbose_name='\u041e\u0431\u044a\u0435\u043a\u0442, \u043a \u043a\u043e\u0442\u043e\u0440\u043e\u043c\u0443 \u0430\u043f\u0441\u0435\u0439\u043b')),
                ('is_active', models.BooleanField(default=True, verbose_name='\u0410\u043f\u0441\u0435\u0439\u043b \u0430\u043a\u0442\u0438\u0432\u0435\u043d')),
                ('is_paid', models.PositiveSmallIntegerField(verbose_name='\u041e\u0431\u044a\u0435\u043a\u0442 \u043e\u043f\u043b\u0430\u0447\u0438\u0432\u0430\u0435\u0442\u0441\u044f', choices=[(0, b'Free'), (1, b'Paid')])),
                ('is_detachable', models.BooleanField(default=False, verbose_name='\u041e\u0442\u0434\u0435\u043b\u044f\u0435\u043c \u043e\u0442 \u043e\u0441\u043d\u043e\u0432\u043d\u043e\u0433\u043e \u043e\u0431\u044a\u0435\u043a\u0442\u0430')),
                ('price', models.PositiveIntegerField(null=True, verbose_name='\u0426\u0435\u043d\u0430', blank=True)),
                ('days_to_buy', models.PositiveSmallIntegerField(null=True, verbose_name='\u0412 \u0442\u0435\u0447\u0435\u043d\u0438\u0435 \u0441\u043a\u043e\u043b\u044c\u043a\u0438\u0445 \u0434\u043d\u0435\u0439 \u0441 \u043d\u0430\u0447\u0430\u043b\u0430 \u0441\u0435\u0441\u0441\u0438\u0438 \u0432\u043e\u0437\u043c\u043e\u0436\u043d\u043e \u043a\u0443\u043f\u0438\u0442\u044c \u0443\u0441\u043b\u0443\u0433\u0443 \u043d\u0430 \u0442\u0435\u043a\u0443\u0449\u0443\u044e \u0441\u0435\u0441\u0441\u0438\u044e?', blank=True)),
                ('days_to_return', models.PositiveSmallIntegerField(null=True, verbose_name='\u0417\u0430 \u0441\u043a\u043e\u043b\u044c\u043a\u043e \u0434\u043d\u0435\u0439 \u0434\u043e \u043a\u043e\u043d\u0446\u0430 \u0441\u0435\u0441\u0441\u0438\u0438 \u043f\u0440\u0435\u043a\u0440\u0430\u0449\u0430\u0442\u044c \u0432\u043e\u0437\u0432\u0440\u0430\u0442 \u0434\u0435\u043d\u0435\u0433 \u0437\u0430 \u0443\u0441\u043b\u0443\u0433\u0443?', blank=True)),
                ('additional_info', jsonfield.fields.JSONField(null=True, blank=True)),
                ('content_type', models.ForeignKey(verbose_name='\u0422\u0438\u043f \u043e\u0431\u044a\u0435\u043a\u0442\u0430, \u043a \u043a\u043e\u0442\u043e\u0440\u043e\u043c\u0443 \u0430\u043f\u0441\u0435\u0439\u043b', to='contenttypes.ContentType')),
                ('upsale', models.ForeignKey(related_name='upsale_links', verbose_name='\u0410\u043f\u0441\u0435\u0439\u043b', to='opro_payments.Upsale')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='upsalelink',
            unique_together=set([('content_type', 'object_id', 'upsale')]),
        ),
    ]
