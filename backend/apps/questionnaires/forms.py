from django import forms
from .models import ProjectQuestionnaire, QuestionnaireTemplate
class ProjectQuestionnaireCreateForm(forms.ModelForm):
    class Meta:
        model = ProjectQuestionnaire
        fields = ["template", "status"]
    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        qs = QuestionnaireTemplate.objects.filter(is_active=True)
        if project and project.project_type:
            qs = qs.filter(project_type__in=[project.project_type, ""])
        self.fields["template"].queryset = qs
