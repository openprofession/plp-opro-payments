# coding: utf-8

from django.contrib import admin
from .admin_forms import UpsaleForm
from .models import Upsale


@admin.register(Upsale)
class UpsaleAdmin(admin.ModelAdmin):
    form = UpsaleForm
