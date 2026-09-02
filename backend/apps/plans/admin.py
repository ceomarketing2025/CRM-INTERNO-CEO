from django.contrib import admin
from .models import ClientPlan, ServicePlan
admin.site.register(ServicePlan)
admin.site.register(ClientPlan)
