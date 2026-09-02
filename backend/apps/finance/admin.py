from django.contrib import admin
from .models import FinanceCategory, FinancialTransaction
admin.site.register(FinanceCategory)
admin.site.register(FinancialTransaction)
