# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('opro_payments', '0003_objectenrollment'),
    ]

    operations = [
        migrations.AddField(
            model_name='upsale',
            name='discount_price',
            field=models.PositiveIntegerField(help_text='\u041f\u0443\u0441\u0442\u043e - \u0435\u0441\u043b\u0438 \u043d\u0435\u0442 \u0441\u043a\u0438\u0434\u043a\u0438.', null=True, verbose_name='\u0421\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c \u0443\u0441\u043b\u0443\u0433\u0438 \u0441\u043e \u0441\u043a\u0438\u0434\u043a\u043e\u0439', blank=True),
        ),
        migrations.AddField(
            model_name='upsale',
            name='image',
            field=models.ImageField(default=None, upload_to=b'upsale_images', verbose_name='\u0418\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 \u0443\u0441\u043b\u0443\u0433\u0438'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='upsalelink',
            name='discount_price',
            field=models.PositiveIntegerField(null=True, verbose_name='\u0421\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c \u0443\u0441\u043b\u0443\u0433\u0438 \u0441\u043e \u0441\u043a\u0438\u0434\u043a\u043e\u0439', blank=True),
        ),
    ]
