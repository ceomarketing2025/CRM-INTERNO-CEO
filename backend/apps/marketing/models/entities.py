from django.conf import settings
from django.db import models
from apps.core.models import TimestampedModel
from .choices import MarketingTaskStatus

class MarketingBrief(TimestampedModel):
    project = models.OneToOneField("projects.Project", on_delete=models.CASCADE, related_name="marketing_brief")
    objective = models.TextField(blank=True)
    target_audience = models.TextField(blank=True)
    channels = models.CharField(max_length=255, blank=True, help_text="Facebook, Instagram, TikTok, Google, etc.")
    tone = models.CharField(max_length=180, blank=True)
    content_pillars = models.TextField(blank=True)
    campaign_notes = models.TextField(blank=True)
    def __str__(self): return f"Brief marketing · {self.project}"

class MarketingTask(TimestampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="marketing_tasks")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="marketing_tasks")
    status = models.CharField(max_length=20, choices=MarketingTaskStatus.choices, default=MarketingTaskStatus.TODO)
    due_date = models.DateField(null=True, blank=True)
    def __str__(self): return self.title
