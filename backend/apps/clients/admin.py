from django.contrib import admin
from .models import Client
@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("client_code", "business_name", "contact_name", "email", "status")
    search_fields = ("client_code", "business_name", "contact_name", "email")
    list_filter = ("status", "client_type")
