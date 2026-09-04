from django.contrib import admin
from .models import FinanceCategory, FinancialTransaction, PersonnelPayment

admin.site.register(FinanceCategory)
admin.site.register(FinancialTransaction)
admin.site.register(PersonnelPayment)
