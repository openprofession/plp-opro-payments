# coding: utf-8

from django.conf import settings
from django.db import models
from django.utils.translation import ugettext_lazy as _
from imagekit.models import ImageSpecField
from imagekit.processors import Resize


class Upsale(models.Model):
    ICON_THUMB_SIZE = (
        getattr(settings, 'UPSALE_ICON_SIZE', (100, 100))[0],
        getattr(settings, 'UPSALE_ICON_SIZE', (100, 100))[1]
    )
    slug = models.SlugField(verbose_name=_(u'Код'), unique=True)
    title = models.CharField(max_length=255, verbose_name=_(u'Название'))
    short_description = models.CharField(
        max_length=80,
        verbose_name=_(u'Короткое описание'),
        help_text=_(u'Отображается везде в интерфейсе рядом с названием')
    )
    description = models.CharField(
        max_length=400,
        verbose_name=_(u'Полное описание'),
        default='',
        blank=True,
        help_text=_(u'Отображается в раскрывающемся окне с подробной информацией по апсейлам')
    )
    additional_info = models.TextField(
        verbose_name=_(u'Дополнительная информация'),
        default='',
        blank=True,
        help_text=_(u'Дополнительная информация для отображения на странице продажи апсейлов. Возможно использование html тегов'))
    icon = models.ImageField(verbose_name=_(u'Иконка'), upload_to='upsale_icons')
    icon_thumbnail = ImageSpecField(source='icon', processors=[Resize(*ICON_THUMB_SIZE)])
    max_per_session = models.PositiveSmallIntegerField(
        default=0,
        verbose_name=_(u'Максимальное количество услуг на 1 сессию'),
        help_text=_(u'0 - если нет ограничений. 1,2,3... - максимальное количество проданных апсейлов к 1 сессии курса')
    )
    price = models.PositiveIntegerField(verbose_name=_(u'Стоимость услуги'), default=0,
                                        help_text=_(u'0 - если бесплатно.'))
    days_to_buy = models.PositiveSmallIntegerField(
        verbose_name=_(u'В течение скольких дней с начала сессии возможно купить услугу на текущую сессию?'),
        blank=True, null=True
    )
    days_to_return = models.PositiveSmallIntegerField(
        verbose_name=_(u'За сколько дней до конца сессии прекращать возврат денег за услугу?'),
        blank=True, null=True
    )
    required = models.CommaSeparatedIntegerField(
        verbose_name=_(u'Необходимые услуги'),
        blank=True,
        null=True,
        max_length=100,
        help_text=_(u'Укажите id апсейлов, без которых текущий апсейл не может быть приобретен, через '
                    u'запятую без пробелов')
    )
    emails = models.CharField(
        verbose_name=_(u'Email ответственных за услугу'),
        blank=True,
        default='',
        max_length=255,
        help_text=_(u'Введите 1 или несколько адресов через запятую. По этим адресам будут '
                    u'приходить уведомления о записи на данную услугу с контактами пользователя.')
    )

    class Meta:
        verbose_name = _(u'Апсейл')
        verbose_name_plural = _(u'Апсейлы')
