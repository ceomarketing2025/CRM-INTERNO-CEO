from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from apps.audit.services import log_activity
from apps.core.decorators import role_required
from apps.projects.models import Project
from .forms import ProjectQuestionnaireCreateForm
from .models import Answer, ProjectQuestionnaire
from .models.choices import AnswerState, QuestionnaireStatus


@role_required("developer")
def create_for_project(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    form = ProjectQuestionnaireCreateForm(request.POST or None, project=project)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.project = project
        obj.created_by = request.user
        if ProjectQuestionnaire.objects.filter(project=project, template=obj.template).exists():
            messages.warning(request, "Ese cuestionario ya existe en el proyecto.")
            return redirect("projects:detail", pk=project.pk)
        obj.save()
        log_activity(request.user, "questionnaires", "create", obj)
        return redirect("questionnaires:fill", pk=obj.pk)
    return render(request, "shared/form.html", {"form": form, "title": "Añadir ficha técnica", "subtitle": project.name})


@role_required("developer")
def fill(request, pk):
    questionnaire = get_object_or_404(
        ProjectQuestionnaire.objects.select_related("project__client", "project__purchased_plan__plan", "template")
        .prefetch_related("template__sections__questions", "answers"),
        pk=pk,
    )
    existing = {a.question_id: a for a in questionnaire.answers.all()}
    sections = questionnaire.template.sections.prefetch_related("questions").all()
    if request.method == "POST":
        with transaction.atomic():
            for section in sections:
                for question in section.questions.all():
                    field = f"q_{question.pk}"
                    state = request.POST.get(f"q_state_{question.pk}", AnswerState.PENDING)
                    if state not in AnswerState.values:
                        state = AnswerState.PENDING
                    if question.question_type == "multi":
                        value_list = request.POST.getlist(field)
                        Answer.objects.update_or_create(
                            questionnaire=questionnaire,
                            question=question,
                            defaults={"state": state, "value_text": "", "value_json": {"values": value_list}, "updated_by": request.user},
                        )
                    else:
                        value = request.POST.get(field, "")
                        Answer.objects.update_or_create(
                            questionnaire=questionnaire,
                            question=question,
                            defaults={"state": state, "value_text": value, "value_json": {}, "updated_by": request.user},
                        )
            questionnaire.status = request.POST.get("questionnaire_status", QuestionnaireStatus.IN_PROGRESS)
            if questionnaire.status not in QuestionnaireStatus.values:
                questionnaire.status = QuestionnaireStatus.IN_PROGRESS
            questionnaire.save(update_fields=["status", "updated_at"])
            project = questionnaire.project
            if questionnaire.status == QuestionnaireStatus.COMPLETE and project.status == "development_intake":
                project.status = "information_ready"
                project.progress = max(project.progress, 55)
                project.summary = "Ficha técnica completada. Resumen de información listo para handoff."
                project.save(update_fields=["status", "progress", "summary", "updated_at"])
            log_activity(request.user, "questionnaires", "save_answers", questionnaire)
        messages.success(request, "Ficha guardada.")
        if questionnaire.status == QuestionnaireStatus.COMPLETE:
            return redirect("handoff:summary", project_pk=questionnaire.project_id)
        return redirect("questionnaires:fill", pk=pk)

    answer_map = {}
    state_map = {}
    for qid, answer in existing.items():
        answer_map[qid] = answer.value_json.get("values", []) if answer.value_json else answer.value_text
        state_map[qid] = answer.state
    return render(request, "questionnaires/fill.html", {
        "questionnaire": questionnaire,
        "sections": sections,
        "answer_map": answer_map,
        "state_map": state_map,
        "answer_states": AnswerState.choices,
    })
