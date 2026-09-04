from django.contrib import admin
from .models import (
    AdCampaign,
    AdvertisingAccount,
    CampaignWeeklyReport,
    GoogleLSAWorkspace,
    MarketingBrief,
    MarketingChecklistItem,
    MarketingDocument,
    MarketingTask,
    MarketingWorkspace,
    SocialMediaDailyLog,
    SocialMediaPlan,
    SocialMediaTracking,
)

for model in [
    MarketingBrief,
    MarketingTask,
    MarketingWorkspace,
    MarketingChecklistItem,
    MarketingDocument,
    GoogleLSAWorkspace,
    AdvertisingAccount,
    AdCampaign,
    CampaignWeeklyReport,
    SocialMediaTracking,
    SocialMediaPlan,
    SocialMediaDailyLog,
]:
    admin.site.register(model)
