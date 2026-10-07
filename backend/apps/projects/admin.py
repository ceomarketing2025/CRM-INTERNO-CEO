from django.contrib import admin
from .models import Project, ProjectAssignment, ProjectNote, ProjectPlanAssignment

admin.site.register(Project)
admin.site.register(ProjectAssignment)
admin.site.register(ProjectNote)
admin.site.register(ProjectPlanAssignment)
