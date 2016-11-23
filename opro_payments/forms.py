# coding: utf-8

from django import forms
from django.utils.translation import ugettext_lazy as _


class CorporatePaymentForm(forms.Form):
    """
    форма приема оплаты для юр.лиц
    """
    full_name = forms.CharField(max_length=127, label=_(u'Имя, Фамилия'))
    org = forms.CharField(max_length=255, label=_(u'Название компании'))
    position = forms.CharField(max_length=127, label=_(u'Должность'))
    email = forms.EmailField(label='Email')
    telephone = forms.CharField(label=_(u'Телефон'))
    students = forms.CharField(label=_(u'Сколько людей планируете обучать?'), widget=forms.NumberInput)
    info = forms.CharField(label=_(u'Комментарий'), widget=forms.Textarea, required=False, max_length=10000)

    def clean_students(self):
        val = self.cleaned_data.get('students')
        if val is not None and not (val.isdigit() and 1 <= int(val) <= 1000000000):
            raise forms.ValidationError(_(u'Пожалуйста, укажите планируемое число слушателей курсов'))
        return val
