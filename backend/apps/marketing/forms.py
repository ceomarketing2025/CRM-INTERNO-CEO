from django import forms
from .models import MarketingBrief, MarketingTask
from apps.accounts.models import UserAccount
class MarketingBriefForm(forms.ModelForm):
    class Meta:
        model = MarketingBrief
        exclude = ["project"]
        widgets = {f: forms.Textarea(attrs={"rows": 3}) for f in ["objective", "target_audience", "content_pillars", "campaign_notes"]}
class MarketingTaskForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(role__in=[UserAccount.Role.MARKETING, UserAccount.Role.MANAGER], is_active=True)
    class Meta:
        model = MarketingTask
        fields = ["project", "title", "description", "assigned_to", "status", "due_date"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "due_date": forms.DateInput(attrs={"type": "date"})}
