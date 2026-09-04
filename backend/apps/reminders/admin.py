from django.contrib import admin
from .models import Meeting, Reminder
admin.site.register(Reminder)
admin.site.register(Meeting)
