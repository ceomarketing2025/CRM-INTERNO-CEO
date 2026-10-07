from django.contrib import admin
from .models import Domain
@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ("domain_name", "client", "registrar", "renewal_date", "status", "annual_cost")
    list_filter = ("status", "auto_renew")
    search_fields = ("domain_name", "client__business_name", "registrar")
