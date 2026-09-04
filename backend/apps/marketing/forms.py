from django import forms
from apps.accounts.models import UserAccount
from .models import AdCampaign, MarketingBrief, MarketingChecklistItem, MarketingDocument, MarketingTask, MarketingWorkspace, SocialMediaDailyLog, SocialMediaPlan, SocialMediaTracking


class MarketingBriefForm(forms.ModelForm):
    class Meta:
        model = MarketingBrief
        exclude = ["project"]
        widgets = {f: forms.Textarea(attrs={"rows": 3}) for f in ["objective", "target_audience", "content_pillars", "campaign_notes"]}


class MarketingTaskForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(role__in=[UserAccount.Role.MARKETING, UserAccount.Role.MANAGER], is_active=True)
        if user and not user.is_manager:
            self.fields["project"].queryset = self.fields["project"].queryset.filter(assignments__user=user, assignments__area="marketing").distinct()
    class Meta:
        model = MarketingTask
        fields = ["project", "title", "description", "assigned_to", "status", "due_date"]
        widgets = {"description": forms.Textarea(attrs={"rows": 3}), "due_date": forms.DateInput(attrs={"type": "date"})}


class MarketingWorkspaceForm(forms.ModelForm):
    class Meta:
        model = MarketingWorkspace
        exclude = ["project", "shared_info_updated_by", "shared_info_updated_at"]
        widgets = {
            "founding_date": forms.DateInput(attrs={"type": "date"}),
            "meeting_summary": forms.Textarea(attrs={"rows": 4}), "social_links": forms.Textarea(attrs={"rows": 3}),
            "company_description": forms.Textarea(attrs={"rows": 4}), "business_hours": forms.Textarea(attrs={"rows": 3}),
            "services": forms.Textarea(attrs={"rows": 4}), "service_areas": forms.Textarea(attrs={"rows": 4}),
            "review_message": forms.Textarea(attrs={"rows": 4}), "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(role__in=[UserAccount.Role.MARKETING, UserAccount.Role.MANAGER], is_active=True)


class ChecklistItemForm(forms.ModelForm):
    class Meta:
        model = MarketingChecklistItem
        fields = ["status", "yes_no", "detail", "due_date"]
        widgets = {"detail": forms.Textarea(attrs={"rows": 2}), "due_date": forms.DateInput(attrs={"type": "date"})}


class MarketingDocumentForm(forms.ModelForm):
    class Meta:
        model = MarketingDocument
        fields = ["title", "document_type", "file", "drive_url", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}


class AdCampaignForm(forms.ModelForm):
    class Meta:
        model = AdCampaign
        fields = ["project", "platform", "name", "account_id", "objective", "campaign_type", "keyword_research", "creative_notes", "manager_review_notes", "start_date", "end_date", "status", "assigned_to", "notes"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}), "end_date": forms.DateInput(attrs={"type": "date"}), "keyword_research": forms.Textarea(attrs={"rows": 3}), "creative_notes": forms.Textarea(attrs={"rows": 3}), "manager_review_notes": forms.Textarea(attrs={"rows": 3}), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(role__in=[UserAccount.Role.MARKETING, UserAccount.Role.MANAGER], is_active=True)
        if user and not user.is_manager:
            self.fields["project"].queryset = self.fields["project"].queryset.filter(assignments__user=user, assignments__area="marketing").distinct()

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "La fecha final no puede ser anterior al inicio.")
        return cleaned


class SocialMediaTrackingForm(forms.ModelForm):
    class Meta:
        model = SocialMediaTracking
        exclude = []
        widgets = {"last_post_gb": forms.DateInput(attrs={"type": "date"}), "gb_notes": forms.Textarea(attrs={"rows": 2}), "notes": forms.Textarea(attrs={"rows": 2})}


class SocialMediaPlanForm(forms.ModelForm):
    class Meta:
        model = SocialMediaPlan
        fields = ["client", "project", "assigned_to", "start_date", "end_date", "active", "next_report_date", "notes"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}), "end_date": forms.DateInput(attrs={"type": "date"}), "next_report_date": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = UserAccount.objects.filter(role__in=[UserAccount.Role.MARKETING, UserAccount.Role.MANAGER], is_active=True)
        if user and not user.is_manager:
            self.fields["project"].queryset = self.fields["project"].queryset.filter(assignments__user=user, assignments__area="marketing").distinct()


class SocialMediaDailyLogForm(forms.ModelForm):
    class Meta:
        model = SocialMediaDailyLog
        fields = ["date", "follow_up", "publication", "post_url", "notes"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 2})}
