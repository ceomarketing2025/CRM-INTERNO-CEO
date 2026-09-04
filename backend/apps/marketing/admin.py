from django.contrib import admin
from .models import AdCampaign, MarketingBrief, MarketingChecklistItem, MarketingDocument, MarketingTask, MarketingWorkspace, SocialMediaDailyLog, SocialMediaPlan, SocialMediaTracking
for model in [MarketingBrief, MarketingTask, MarketingWorkspace, MarketingChecklistItem, MarketingDocument, AdCampaign, SocialMediaTracking, SocialMediaPlan, SocialMediaDailyLog]:
    admin.site.register(model)
