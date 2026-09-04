from django.contrib import admin
from .models import (
    FinanceCategory,
    FinancialTransaction,
    OperatingExpense,
    PersonnelPayment,
    ProjectPayment,
    SubscriptionPayment,
)

admin.site.register(FinanceCategory)
admin.site.register(FinancialTransaction)
admin.site.register(OperatingExpense)
admin.site.register(PersonnelPayment)
admin.site.register(ProjectPayment)
admin.site.register(SubscriptionPayment)
