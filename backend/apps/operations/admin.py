from django.contrib import admin
from .models import (
    CredentialPurchase,
    DomainHostingRecord,
    GeneralManagementRecord,
    ProductionRecord,
    ProjectCredential,
    WebProductionCounty,
    WebProductionCountyService,
    WebProductionCity,
    WebProductionPage,
    WebProductionSheet,
)

admin.site.register(GeneralManagementRecord)
admin.site.register(CredentialPurchase)
admin.site.register(DomainHostingRecord)
admin.site.register(ProjectCredential)
admin.site.register(ProductionRecord)
admin.site.register(WebProductionSheet)
admin.site.register(WebProductionPage)
admin.site.register(WebProductionCounty)
admin.site.register(WebProductionCountyService)
admin.site.register(WebProductionCity)
