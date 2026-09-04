from django.contrib import admin
from .models import (
    CredentialPurchase,
    GeneralManagementRecord,
    ProductionRecord,
    WebProductionCounty,
    WebProductionCountyService,
    WebProductionCity,
    WebProductionPage,
    WebProductionSheet,
)

admin.site.register(GeneralManagementRecord)
admin.site.register(CredentialPurchase)
admin.site.register(ProductionRecord)
admin.site.register(WebProductionSheet)
admin.site.register(WebProductionPage)
admin.site.register(WebProductionCounty)
admin.site.register(WebProductionCountyService)

admin.site.register(WebProductionCity)
