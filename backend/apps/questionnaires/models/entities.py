from django.conf import settings
from django.db import models
from apps.core.models import TimestampedModel
from .choices import AnswerState, QuestionType, QuestionnaireStatus


class QuestionnaireTemplate(TimestampedModel):
    name = models.CharField(max_length=180)
    code = models.SlugField(max_length=100, unique=True)
    project_type = models.CharField(max_length=30, blank=True, help_text="website, software, social_media, etc.")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class QuestionnaireSection(TimestampedModel):
    template = models.ForeignKey(QuestionnaireTemplate, on_delete=models.CASCADE, related_name="sections")
    title = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.template.name} · {self.title}"


class Question(TimestampedModel):
    section = models.ForeignKey(QuestionnaireSection, on_delete=models.CASCADE, related_name="questions")
    key = models.SlugField(max_length=120)
    text = models.TextField()
    help_text = models.TextField(blank=True)
    question_type = models.CharField(max_length=20, choices=QuestionType.choices, default=QuestionType.TEXT)
    required = models.BooleanField(default=False)
    options = models.JSONField(default=list, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        constraints = [models.UniqueConstraint(fields=["section", "key"], name="unique_question_key_per_section_v2")]

    def __str__(self):
        return self.text[:80]


class ProjectQuestionnaire(TimestampedModel):
    project = models.ForeignKey("projects.Project", on_delete=models.CASCADE, related_name="questionnaires")
    template = models.ForeignKey(QuestionnaireTemplate, on_delete=models.PROTECT, related_name="project_instances")
    status = models.CharField(max_length=20, choices=QuestionnaireStatus.choices, default=QuestionnaireStatus.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_questionnaires")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "template"], name="unique_template_per_project_v2")]

    def __str__(self):
        return f"{self.project} · {self.template.name}"


class Answer(TimestampedModel):
    questionnaire = models.ForeignKey(ProjectQuestionnaire, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="answers")
    state = models.CharField(max_length=20, choices=AnswerState.choices, default=AnswerState.PENDING)
    value_text = models.TextField(blank=True)
    value_json = models.JSONField(default=dict, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="updated_question_answers")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["questionnaire", "question"], name="unique_answer_per_question_v2")]

    def __str__(self):
        return f"{self.questionnaire} · {self.question.key}"
