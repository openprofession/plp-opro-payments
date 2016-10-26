# coding: utf-8

from django import forms
from django.core.validators import validate_email
from django.utils.translation import ugettext_lazy as _
from .models import Upsale


class UpsaleForm(forms.ModelForm):
    def _check_str_limits(self, attr, len_min, len_max):
        val = self.cleaned_data.get(attr)
        if val and not (20 <= len(val) <= 80):
            raise forms.ValidationError(_(u'Длина текста должна быть от {min} до {max} символов').format(
                min=len_min, max=len_max
            ))
        return val

    def clean_short_description(self):
        return self._check_str_limits('short_description', 20, 80)

    def clean_description(self):
        return self._check_str_limits('description', 60, 400)

    def clean_price(self):
        val = self.cleaned_data.get('price')
        if val is not None:
            if not (0 <= val <= 999999):
                raise forms.ValidationError(_(u'Введите число от 0 до 999999'))
        return val

    def clean_icon(self):
        val = self.cleaned_data.get('icon')
        if val and hasattr(val, 'image'):
            image = val.image
            if val._get_size() > (2**10)**2:
                raise forms.ValidationError(_(u'Размер изображения должен быть не больше 1Мб'))
            if image.format != 'PNG':
                raise forms.ValidationError(_(u'Выберите изображение формата png'))
            if image.height > 1000 or image.width > 1000:
                raise forms.ValidationError(_(u'Разрешение изображения должно быть не больше 1000x1000px'))
        return val

    def clean_required(self):
        val = self.cleaned_data.get('required')
        if not val:
            return val
        try:
            field = self.Meta.model._meta.get_field('required')
            field.run_validators(val)
        except forms.ValidationError:
            return val
        else:
            ids_set = set([int(i) for i in val.split(',')])
            existing_ids_set = set(Upsale.objects.filter(id__in=ids_set).values_list('id', flat=True))
            diff = ids_set - existing_ids_set
            if diff:
                raise forms.ValidationError(_(u'В списке содержатся id апсейлов, которых не в системе: %s') % \
                    ', '.join(map(str, diff)))
            return val

    def clean_emails(self):
        vals = self.cleaned_data.get('emails') or ''
        emails = [i.strip() for i in vals.split(',') if i.strip()]
        bad_emails = []
        for e in emails:
            try:
                validate_email(e)
            except forms.ValidationError:
                bad_emails.append(e)
        if bad_emails:
            raise forms.ValidationError(_(u'В списке содержатся невалидные емейлы: %s') % u', '.join(bad_emails))
        return vals

    class Meta:
        model = Upsale
        fields = '__all__'
        widgets = {
            'description': forms.Textarea,
        }
