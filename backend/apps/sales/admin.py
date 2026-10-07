from django.contrib import admin
from .models import ContactAttempt, FollowUp, Lead, LeadAssignmentHistory, SalesMeeting

admin.site.register([Lead, LeadAssignmentHistory, ContactAttempt, FollowUp, SalesMeeting])
