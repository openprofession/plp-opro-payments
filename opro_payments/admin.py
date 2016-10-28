# coding: utf-8

from django.contrib import admin
from .admin_forms import UpsaleForm, UpsaleLinkForm
from .models import Upsale, UpsaleLink


@admin.register(Upsale)
class UpsaleAdmin(admin.ModelAdmin):
    form = UpsaleForm


@admin.register(UpsaleLink)
class UpsaleLinkAdmin(admin.ModelAdmin):
    form = UpsaleLinkForm
