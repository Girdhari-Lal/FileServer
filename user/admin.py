from django import forms
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from django.core.exceptions import ValidationError
from user.models import MyUser

class UserAdmin(BaseUserAdmin):
    list_display = ["email", "name", "date_of_birth", "is_admin"]
    list_filter = ["is_admin"]

    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("Personal info", {"fields": ["name", "date_of_birth"]}),
        ("Permissions", {"fields": ["is_admin", "user_type"]}),
    ]

    add_fieldsets = [
        (
            None,
            {
                "classes": ["wide"],
                "fields": ["email", "name", "date_of_birth", "password1", "password2", "user_type"],
            },
        ),
    ]

    search_fields = ["email", "name"]
    ordering = ["email"]
    filter_horizontal = []


admin.site.register(MyUser, UserAdmin)
admin.site.unregister(Group)
