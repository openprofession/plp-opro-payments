# coding: utf-8

from django import forms
from django.contrib.contenttypes.models import ContentType
from django.core.validators import validate_email
from django.utils.translation import ugettext_lazy as _, ungettext_lazy
import autocomplete_light
from .models import Upsale, UpsaleLink, ObjectEnrollment


class UpsaleFormCheckerMixin(object):
    def _check_str_limits(self, attr, len_min, len_max):
        val = self.cleaned_data.get(attr)
        if val and not (20 <= len(val) <= 80):
            raise forms.ValidationError(_(u'Длина текста должна быть от {min} до {max} символов').format(
                min=len_min, max=len_max
            ))
        return val

    def _check_value_limits(self, attr, min_val, max_val):
        val = self.cleaned_data.get(attr)
        if val is not None:
            if not (min_val <= val <= max_val):
                raise forms.ValidationError(_(u'Введите число от {min_val} до {max_val}'.format(
                    min_val=min_val, max_val=max_val)))
        return val

    def _check_image(self, attr, max_file_size=None, types=None, max_size=None):
        val = self.cleaned_data.get(attr)
        if val and hasattr(val, 'image'):
            image = val.image
            if max_file_size is not None and val._get_size() > max_file_size * (2**10)**2:
                raise forms.ValidationError(_(u'Размер изображения должен быть не больше {}Мб').format(max_file_size))
            if types is not None and image.format not in types:
                raise forms.ValidationError(
                    ungettext_lazy(u'Допустимый формат: %s', u'Допустимые форматы: %s', len(types)) % u', '.join(types))
            if max_size is not None and (image.height > max_size[1] or image.width > max_size[0]):
                raise forms.ValidationError(_(u'Разрешение изображения должно быть не больше {}x{}px').format(*max_size))
        return val

    def _check_discount_less_than_price(self):
        price = self.cleaned_data.get('price')
        discount_price = self.cleaned_data.get('discount_price')
        if price is not None and discount_price is not None:
            if discount_price > price:
                raise forms.ValidationError(_(u'Цена со скидкой превышает цену продукта'))


class UpsaleForm(UpsaleFormCheckerMixin, forms.ModelForm):
    def clean_short_description(self):
        return self._check_str_limits('short_description', 20, 80)

    def clean_description(self):
        return self._check_str_limits('description', 60, 400)

    def clean_price(self):
        return self._check_value_limits('price', 0, 999999)

    def clean_discount_price(self):
        return self._check_value_limits('discount_price', 0, 999999)

    def clean_icon(self):
        return self._check_image('icon', max_file_size=1, types=['PNG'], max_size=[1000, 1000])

    def clean_image(self):
        return self._check_image('image', types=['PNG', 'JPEG'], max_size=[1000, 1000])

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

    def clean(self):
        self._check_discount_less_than_price()
        return super(UpsaleForm, self).clean()

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


class UpsaleLinkForm(UpsaleFormCheckerMixin, forms.ModelForm):
    autocomplete_field = autocomplete_light.ChoiceField(
        autocomplete='UpsaleLinkMulticomplete',
        label=UpsaleLink._meta.get_field('object_id').verbose_name,
    )

    def __init__(self, *args, **kwargs):
        super(UpsaleLinkForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['autocomplete_field'].initial = '%s-%s' % (self.instance.content_type.id,
                                                                   self.instance.object_id)
        self.fields['upsale'] = autocomplete_light.ModelChoiceField(autocomplete='UpsaleAutocomplete')
        self.fields['content_type'].empty_label = None

    def clean_price(self):
        return self._check_value_limits('price', 0, 999999)

    def clean_discount_price(self):
        return self._check_value_limits('discount_price', 0, 999999)

    def clean(self):
        self._check_discount_less_than_price()
        data = super(UpsaleLinkForm, self).clean()
        autocomplete = data.get('autocomplete_field')
        content_type = data.get('content_type')
        if autocomplete and content_type:
            ctype_id = autocomplete.split('-')[0]
            ct = ContentType.objects.get(id=ctype_id)
            if ct != content_type:
                raise forms.ValidationError(_(u'Тип объекта не совпадает с выбранным объектом'))
        return data

    def clean_additional_info(self):
        # запрет изменения already_sent
        data = self.cleaned_data.get('additional_info')
        if data and self.instance.pk:
            try:
                old_data = self.instance._meta.model.objects.get(pk=self.instance.pk).additional_info or {}
                sent_val = data.get('promo', {}).get('already_sent')
                old_sent_val = old_data.get('promo', {}).get('already_sent', 0)
                if sent_val != old_sent_val:
                    tmp = data.get('promo', {})
                    tmp['already_sent'] = old_sent_val
                    data['promo'] = tmp
            except ValueError:
                pass
        if data and not self.instance.pk:
            if 'promo' in data and isinstance(data['promo'], dict):
                data['promo']['already_sent'] = 0
        return data

    class Meta:
        model = UpsaleLink
        fields = '__all__'
        widgets = {
            'object_id': forms.HiddenInput,
        }
        js = ('dependant_autocomplete.js',)


class ObjectEnrollmentForm(forms.ModelForm):
    is_active = forms.ChoiceField(label=ObjectEnrollment._meta.get_field('is_active').verbose_name,
                                  choices=((False, 'Inactive'), (True, 'Active')), required=False)

    def clean(self):
        data = super(ObjectEnrollmentForm, self).clean()
        enrollment_type = data.get('enrollment_type')
        payment_type = data.get('payment_type')
        if enrollment_type is not None and payment_type is not None:
            paid_enrollment = enrollment_type == ObjectEnrollment.ENROLLMENT_TYPE_CHOICES.paid
            paid = payment_type != ObjectEnrollment.PAYMENT_TYPE_CHOICES.none
            if paid_enrollment and not paid or paid and not paid_enrollment:
                raise forms.ValidationError(_(u'Тип записи несовместим со способом платежа'))
        return data

    class Meta:
        model = ObjectEnrollment
        fields = '__all__'
        widgets = {
            'user': autocomplete_light.ChoiceWidget(autocomplete='UserAutocomplete'),
        }
