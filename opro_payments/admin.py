# coding: utf-8

from django.contrib import admin
from .admin_forms import UpsaleForm, UpsaleLinkForm, ObjectEnrollmentForm
from .models import Upsale, UpsaleLink, ObjectEnrollment


@admin.register(Upsale)
class UpsaleAdmin(admin.ModelAdmin):
    form = UpsaleForm


@admin.register(UpsaleLink)
class UpsaleLinkAdmin(admin.ModelAdmin):
    form = UpsaleLinkForm


@admin.register(ObjectEnrollment)
class ObjectEnrollmentAdmin(admin.ModelAdmin):
    form = ObjectEnrollmentForm
    search_fields = ('user__username', 'user__email')

    def formfield_for_dbfield(self, db_field, **kwargs):
        field = super(ObjectEnrollmentAdmin, self).formfield_for_dbfield(db_field, **kwargs)
        if db_field.name == 'upsale':
            field.queryset = field.queryset.filter(is_active=True)
        return field
