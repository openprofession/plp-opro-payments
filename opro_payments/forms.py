# coding: utf-8

from django import forms
from django.utils.translation import ugettext_lazy as _

class GiftForm(forms.Form):

    date_formats = ['%d.%m.%Y']

    gift_sender = forms.CharField(
        label=u'Ваше имя',
        widget=forms.TextInput(attrs={'class':'input-field'})
    )
    gift_sender_email = forms.CharField(
        label=u'Ваш e-mail',
        widget=forms.TextInput(attrs={'class':'input-field'})
    )
    gift_receiver = forms.CharField(
        label=u'Имя получателя подарка',
        widget=forms.TextInput(attrs={'class':'input-field'})
    )
    gift_receiver_email = forms.CharField(
        label=u'E-mail получателя подарка',
        widget=forms.TextInput(attrs={'class':'input-field'})
    )
    promocode = forms.CharField(
        label=u'Промокод',
        required=False,
        widget=forms.TextInput(attrs={'class':'input-field'})
    )    
    mail_template = forms.CharField(
        label=u'Текст поздравления',
        required=False,
        widget=forms.Textarea()
    )  
    mail_template = forms.CharField(
        label=u'Текст поздравления',
        required=False,
        widget=forms.Textarea(attrs={'class':'textarea','placeholder': 'Текст поздравления'})
    )          
    send_date = forms.DateField(
        label=u'Дата отправки',
        input_formats=date_formats,
        widget=forms.DateInput(attrs={'class':'datepicker-input','placeholder': 'Когда вы хотите подарить подарок?'})
    )
    
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
