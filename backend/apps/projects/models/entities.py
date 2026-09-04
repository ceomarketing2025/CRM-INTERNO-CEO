from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from apps.core.models import TimestampedModel
from .choices import AssignmentArea, AssignmentStatus, Priority, ProjectStatus, ProjectType


class Project(TimestampedModel):
    project_code = models.CharField(max_length=20, unique=True, blank=True)
    client = models.ForeignKey("clients.Client", on_delete=models.CASCADE, related_name="projects")
    purchased_plan = models.ForeignKey("plans.ClientPlan", null=True, blank=True, on_delete=models.SET_NULL, related_name="projects")
    name = models.CharField(max_length=180)
    project_type = models.CharField(max_length=30, choices=ProjectType.choices)
    status = models.CharField(max_length=30, choices=ProjectStatus.choices, default=ProjectStatus.ACTIVE)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.MEDIUM)
    progress = models.PositiveSmallIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    summary = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_projects_v2")

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status"]), models.Index(fields=["project_type"])]

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        super().save(*args, **kwargs)
        if is_new and not self.project_code:
            self.project_code = f"PRJ-{self.pk:05d}"
            type(self).objects.filter(pk=self.pk).update(project_code=self.project_code)

    @property
    def workflow_position(self):
        return self.progress


    def __str__(self):
        return f"{self.project_code or 'PRJ'} · {self.name}"


class ProjectAssignment(TimestampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="assignments")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assigned_projects_v2")
    area = models.CharField(max_length=20, choices=AssignmentArea.choices)
    status = models.CharField(max_length=20, choices=AssignmentStatus.choices, default=AssignmentStatus.ASSIGNED)
    responsibility = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "user", "area"], name="unique_project_user_area_v2")]

    def __str__(self):
        return f"{self.project} · {self.user.email}"


class ProjectNote(TimestampedModel):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_notes")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="project_notes_v2")
    note = models.TextField()
    is_internal = models.BooleanField(default=True)

    def __str__(self):
        return f"Nota · {self.project.project_code}"
