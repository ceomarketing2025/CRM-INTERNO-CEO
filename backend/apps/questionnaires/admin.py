from django.contrib import admin
from .models import Answer, ProjectQuestionnaire, Question, QuestionnaireSection, QuestionnaireTemplate
admin.site.register(QuestionnaireTemplate)
admin.site.register(QuestionnaireSection)
admin.site.register(Question)
admin.site.register(ProjectQuestionnaire)
admin.site.register(Answer)
