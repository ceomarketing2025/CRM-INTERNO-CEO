from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.core.exceptions import PermissionDenied
from apps.audit.models import ActivityLog
from apps.audit.services import log_activity
from apps.core.decorators import role_required
from apps.operations.models import WebProductionSheet
from apps.projects.models import Project
from apps.plans.models.choices import PlanDepartment
from apps.projects.selectors import can_access_project, projects_for_area
from apps.projects.services import sync_project_area_records
from .forms import ProjectQuestionnaireCreateForm
from .models import Answer, ProjectQuestionnaire, QuestionnaireTemplate
from .models.choices import AnswerState, QuestionnaireStatus
from .services import (
    WEBSITE_TEMPLATE_CODE,
    save_key_answer,
    sync_website_shared_to_marketing,
    website_answer_payload,
    website_questionnaire_progress,
)


def _clean(value):
    return (value or "").strip()


def _yes_no(value):
    return value if value in {"yes", "no"} else ""


def _indexed_rows(request, prefix, fields):
    """Read dynamic rows sent as prefix_<field>[] while preserving row position."""
    columns = {field: request.POST.getlist(f"{prefix}_{field}") for field in fields}
    count = max([len(values) for values in columns.values()] or [0])
    rows = []
    for index in range(count):
        row = {field: _clean(columns[field][index]) if index < len(columns[field]) else "" for field in fields}
        if any(row.values()):
            rows.append(row)
    return rows


def _status_for(condition, negative=False):
    return bool(condition), bool(negative and condition)


def _website_save(questionnaire, request):
    user = request.user

    company_description = _clean(request.POST.get("company_description"))
    save_key_answer(
        questionnaire=questionnaire, key="company_description", user=user,
        value_text=company_description, complete=bool(company_description),
    )

    slogan_mode = request.POST.get("slogan_mode", "")
    slogan_text = _clean(request.POST.get("slogan_text"))
    slogan_complete = slogan_mode == "none" or (slogan_mode in {"existing", "create"} and bool(slogan_text))
    slogan_label = {
        "existing": f"Slogan actual: {slogan_text}",
        "create": f"Slogan creado/propuesto: {slogan_text}",
        "none": "No crear slogan",
    }.get(slogan_mode, slogan_text)
    save_key_answer(
        questionnaire=questionnaire, key="slogan", user=user,
        value_text=slogan_label, value_json={"mode": slogan_mode, "text": slogan_text},
        complete=slogan_complete, negative=slogan_mode == "none",
    )

    mission_has = _yes_no(request.POST.get("mission_has"))
    mission = _clean(request.POST.get("mission_text"))
    vision = _clean(request.POST.get("vision_text"))
    mission_origin = _clean(request.POST.get("mission_origin"))
    mission_clients = _clean(request.POST.get("mission_clients"))
    vision_future = _clean(request.POST.get("vision_future"))
    vision_legacy = _clean(request.POST.get("vision_legacy"))
    mission_complete = (
        mission_has == "yes" and bool(mission and vision)
    ) or (
        mission_has == "no" and all([mission_origin, mission_clients, vision_future, vision_legacy])
    )
    mission_summary = ""
    if mission_has == "yes":
        mission_summary = f"Misión: {mission}\nVisión: {vision}".strip()
    elif mission_has == "no":
        mission_summary = "Información recopilada para crear misión y visión"
    save_key_answer(
        questionnaire=questionnaire, key="has_mission_vision", user=user,
        value_text=mission_summary,
        value_json={
            "has": mission_has, "mission": mission, "vision": vision,
            "mission_origin": mission_origin, "mission_clients": mission_clients,
            "vision_future": vision_future, "vision_legacy": vision_legacy,
        }, complete=mission_complete, negative=False,
    )

    team_include = _yes_no(request.POST.get("team_include"))
    team_scope = _clean(request.POST.get("team_scope"))
    team_details = _clean(request.POST.get("team_details"))
    team_complete = team_include == "no" or (team_include == "yes" and bool(team_scope and team_details))
    team_summary = "No incluir Team" if team_include == "no" else f"{team_scope}: {team_details}".strip(": ")
    save_key_answer(
        questionnaire=questionnaire, key="show_team", user=user,
        value_text=team_summary,
        value_json={"include": team_include, "scope": team_scope, "details": team_details},
        complete=team_complete, negative=team_include == "no",
    )

    service_names = request.POST.getlist("service_name")
    excluded_indexes = set(request.POST.getlist("service_excluded"))
    primary_index = request.POST.get("service_primary", "")
    services = []
    for index, raw_name in enumerate(service_names):
        name = _clean(raw_name)
        if not name:
            continue
        services.append({
            "name": name,
            "primary": str(index) == str(primary_index),
            "excluded": str(index) in excluded_indexes,
        })
    # Enforce at most one primary server-side.
    found_primary = False
    for item in services:
        if item["primary"] and not item["excluded"] and not found_primary:
            found_primary = True
        else:
            item["primary"] = False
    service_lines = []
    for item in services:
        tags = []
        if item["primary"]:
            tags.append("PRINCIPAL")
        if item["excluded"]:
            tags.append("DEJAR FUERA")
        service_lines.append(f"{item['name']}" + (f" ({', '.join(tags)})" if tags else ""))
    save_key_answer(
        questionnaire=questionnaire, key="main_services", user=user,
        value_text="\n".join(service_lines), value_json={"items": services}, complete=bool(services),
    )

    area_types = request.POST.getlist("area_type")
    area_names = request.POST.getlist("area_name")
    areas = []
    for index, raw_name in enumerate(area_names):
        name = _clean(raw_name)
        if not name:
            continue
        area_type = area_types[index] if index < len(area_types) and area_types[index] in {"state", "county", "city"} else "city"
        areas.append({"type": area_type, "name": name})
    area_labels = {"state": "Estado", "county": "Condado", "city": "Ciudad"}
    save_key_answer(
        questionnaire=questionnaire, key="service_areas", user=user,
        value_text="\n".join(f"{area_labels.get(item['type'], 'Área')}: {item['name']}" for item in areas),
        value_json={"items": areas}, complete=bool(areas),
    )

    coverage_miles = _clean(request.POST.get("coverage_miles"))
    coverage_complete = coverage_miles.isdigit() and int(coverage_miles) >= 0
    save_key_answer(
        questionnaire=questionnaire, key="coverage", user=user,
        value_text=f"{coverage_miles} millas alrededor" if coverage_miles else "",
        value_json={"miles": coverage_miles}, complete=coverage_complete,
    )

    expansion_answer = _yes_no(request.POST.get("expansion_answer"))
    expansion_types = request.POST.getlist("expansion_type")
    expansion_names = request.POST.getlist("expansion_name")
    expansion_areas = []
    for index, raw_name in enumerate(expansion_names):
        name = _clean(raw_name)
        if not name:
            continue
        area_type = expansion_types[index] if index < len(expansion_types) and expansion_types[index] in {"state", "county", "city"} else "city"
        expansion_areas.append({"type": area_type, "name": name})
    expansion_complete = expansion_answer == "no" or (expansion_answer == "yes" and bool(expansion_areas))
    expansion_text = "No planea expansión" if expansion_answer == "no" else "\n".join(
        f"{area_labels.get(item['type'], 'Área')}: {item['name']}" for item in expansion_areas
    )
    save_key_answer(
        questionnaire=questionnaire, key="future_expansion", user=user,
        value_text=expansion_text, value_json={"answer": expansion_answer, "areas": expansion_areas},
        complete=expansion_complete, negative=expansion_answer == "no",
    )

    seo_strategy = request.POST.get("seo_page_strategy", "")
    seo_complete = seo_strategy in {"study", "client_services"}
    seo_text = {
        "study": "Realizar estudio y crear páginas según tendencia / oportunidad SEO",
        "client_services": "Crear páginas con los servicios indicados por el cliente",
    }.get(seo_strategy, "")
    save_key_answer(
        questionnaire=questionnaire, key="seo_page_strategy", user=user,
        value_text=seo_text, value_json={"strategy": seo_strategy}, complete=seo_complete,
    )

    is_24_7 = _yes_no(request.POST.get("is_24_7"))
    start_time = _clean(request.POST.get("hours_start"))
    start_period = request.POST.get("hours_start_period", "AM") if request.POST.get("hours_start_period") in {"AM", "PM"} else "AM"
    end_time = _clean(request.POST.get("hours_end"))
    end_period = request.POST.get("hours_end_period", "PM") if request.POST.get("hours_end_period") in {"AM", "PM"} else "PM"
    hours_complete = is_24_7 == "yes" or bool(start_time and end_time)
    hours_text = "24/7" if is_24_7 == "yes" else (f"{start_time} {start_period} - {end_time} {end_period}" if start_time and end_time else "")
    save_key_answer(
        questionnaire=questionnaire, key="business_hours", user=user,
        value_text=hours_text,
        value_json={"start": start_time, "start_period": start_period, "end": end_time, "end_period": end_period},
        complete=hours_complete,
    )
    save_key_answer(
        questionnaire=questionnaire, key="is_24_7", user=user,
        value_text="Sí" if is_24_7 == "yes" else ("No" if is_24_7 == "no" else ""),
        value_json={"answer": is_24_7}, complete=is_24_7 in {"yes", "no"}, negative=is_24_7 == "no",
    )

    phone_numbers = request.POST.getlist("phone_number")
    phone_primary = request.POST.get("phone_primary", "")
    phones = []
    for index, raw_number in enumerate(phone_numbers):
        number = _clean(raw_number)
        if number:
            phones.append({"number": number, "primary": str(index) == str(phone_primary)})
    if phones and not any(item["primary"] for item in phones):
        phones[0]["primary"] = True
    save_key_answer(
        questionnaire=questionnaire, key="contact_numbers", user=user,
        value_text="\n".join(f"{item['number']}{' (Principal)' if item['primary'] else ''}" for item in phones),
        value_json={"numbers": phones}, complete=bool(phones),
    )

    social_has = _yes_no(request.POST.get("social_has"))
    social_keys = ["facebook", "instagram", "tiktok", "youtube", "twitter", "yelp", "linkedin", "nextdoor"]
    networks = {}
    for key in social_keys:
        if request.POST.get(f"social_enabled_{key}") == "1":
            networks[key] = _clean(request.POST.get(f"social_url_{key}"))
    custom_names = request.POST.getlist("social_custom_name")
    custom_urls = request.POST.getlist("social_custom_url")
    custom_social = []
    for index in range(max(len(custom_names), len(custom_urls))):
        name = _clean(custom_names[index]) if index < len(custom_names) else ""
        url = _clean(custom_urls[index]) if index < len(custom_urls) else ""
        if name or url:
            custom_social.append({"name": name, "url": url})
    has_social_link = any(networks.values()) or any(item.get("url") for item in custom_social)
    social_complete = social_has == "no" or (social_has == "yes" and has_social_link)
    social_labels = {
        "facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube",
        "twitter": "X / Twitter", "yelp": "Yelp", "linkedin": "LinkedIn", "nextdoor": "Nextdoor",
    }
    social_lines = [f"{social_labels[key]}: {url}" for key, url in networks.items() if url]
    social_lines += [f"{item['name'] or 'Otra red'}: {item['url']}" for item in custom_social if item.get("url")]
    social_text = "No tiene redes sociales" if social_has == "no" else "\n".join(social_lines)
    save_key_answer(
        questionnaire=questionnaire, key="has_social", user=user,
        value_text=social_text, value_json={"has": social_has, "networks": networks, "custom": custom_social},
        complete=social_complete, negative=social_has == "no",
    )

    webmail_has = _yes_no(request.POST.get("webmail_has"))
    webmail_email = _clean(request.POST.get("webmail_email"))
    webmail_ref = _clean(request.POST.get("webmail_secure_reference_url"))
    webmail_complete = webmail_has == "no" or (webmail_has == "yes" and bool(webmail_email))
    save_key_answer(
        questionnaire=questionnaire, key="has_webmail", user=user,
        value_text=webmail_email if webmail_has == "yes" else ("No tiene webmail" if webmail_has == "no" else ""),
        value_json={"has": webmail_has, "email": webmail_email, "secure_reference_url": webmail_ref},
        complete=webmail_complete, negative=webmail_has == "no",
    )

    gbp_mode = request.POST.get("gbp_mode", "")
    gbp_link = _clean(request.POST.get("gbp_link"))
    gbp_notes = _clean(request.POST.get("gbp_notes"))
    gbp_complete = gbp_mode in {"create", "no"} or (gbp_mode == "existing" and bool(gbp_link))
    gbp_text = {
        "existing": f"Ya tiene Google Business: {gbp_link}",
        "create": "Crear Google Business",
        "no": "No tiene / no crear",
    }.get(gbp_mode, "")
    save_key_answer(
        questionnaire=questionnaire, key="has_gbp", user=user,
        value_text=gbp_text, value_json={"mode": gbp_mode, "link": gbp_link, "notes": gbp_notes},
        complete=gbp_complete, negative=gbp_mode == "no",
    )

    website_has = _yes_no(request.POST.get("website_has"))
    website_url = _clean(request.POST.get("website_url"))
    website_complete = website_has == "no" or (website_has == "yes" and bool(website_url))
    save_key_answer(
        questionnaire=questionnaire, key="has_website", user=user,
        value_text=website_url if website_has == "yes" else ("No tiene sitio web" if website_has == "no" else ""),
        value_json={"has": website_has, "url": website_url}, complete=website_complete, negative=website_has == "no",
    )

    cert_has = _yes_no(request.POST.get("certifications_has"))
    cert_detail = _clean(request.POST.get("certifications_detail"))
    cert_complete = cert_has == "no" or (cert_has == "yes" and bool(cert_detail))
    save_key_answer(
        questionnaire=questionnaire, key="certifications", user=user,
        value_text=cert_detail if cert_has == "yes" else ("No tiene certificaciones" if cert_has == "no" else ""),
        value_json={"has": cert_has, "detail": cert_detail}, complete=cert_complete, negative=cert_has == "no",
    )

    warranty_has = _yes_no(request.POST.get("warranties_has"))
    warranty_detail = _clean(request.POST.get("warranties_detail"))
    warranty_complete = warranty_has == "no" or (warranty_has == "yes" and bool(warranty_detail))
    save_key_answer(
        questionnaire=questionnaire, key="warranties", user=user,
        value_text=warranty_detail if warranty_has == "yes" else ("No ofrece garantía" if warranty_has == "no" else ""),
        value_json={"has": warranty_has, "detail": warranty_detail}, complete=warranty_complete, negative=warranty_has == "no",
    )

    experience_years = _clean(request.POST.get("experience_years"))
    experience_complete = experience_years.isdigit()
    save_key_answer(
        questionnaire=questionnaire, key="experience_years", user=user,
        value_text=experience_years, value_json={"years": experience_years}, complete=experience_complete,
    )

    internal_notes = _clean(request.POST.get("internal_meeting_notes"))
    save_key_answer(
        questionnaire=questionnaire, key="internal_meeting_notes", user=user,
        value_text=internal_notes, complete=bool(internal_notes),
    )

    progress = website_questionnaire_progress(questionnaire)
    questionnaire.status = QuestionnaireStatus.COMPLETE if progress["percent"] == 100 else QuestionnaireStatus.IN_PROGRESS
    questionnaire.save(update_fields=["status", "updated_at"])
    sync_website_shared_to_marketing(questionnaire, user)
    return progress


def _website_fill_context(questionnaire):
    payload = website_answer_payload(questionnaire)
    progress = website_questionnaire_progress(questionnaire)
    return {
        "questionnaire": questionnaire,
        "data": payload,
        "progress": progress,
        "social_networks": [
            ("facebook", "Facebook"), ("instagram", "Instagram"), ("tiktok", "TikTok"),
            ("youtube", "YouTube"), ("twitter", "X / Twitter"), ("yelp", "Yelp"),
            ("linkedin", "LinkedIn"), ("nextdoor", "Nextdoor"),
        ],
    }


@role_required("developer")
def development_dashboard(request):
    projects = projects_for_area("development").order_by("-updated_at", "-created_at")

    rows = []
    for project in projects:
        sync_project_area_records(project, request.user)
        questionnaire = ProjectQuestionnaire.objects.filter(project=project).select_related("template").order_by("id").first()
        technical_progress = website_questionnaire_progress(questionnaire) if questionnaire and questionnaire.template.code == WEBSITE_TEMPLATE_CODE else {
            "complete": 1 if questionnaire and questionnaire.status == QuestionnaireStatus.COMPLETE else 0,
            "total": 1 if questionnaire else 0,
            "percent": 100 if questionnaire and questionnaire.status == QuestionnaireStatus.COMPLETE else 0,
        }
        sheet = WebProductionSheet.objects.filter(project=project).prefetch_related("pages", "counties__services", "cities").first()
        last_log = ActivityLog.objects.filter(metadata__project_id=project.pk).select_related("user").first()
        if sheet:
            all_rows = list(sheet.pages.all()) + list(sheet.counties.all()) + [s for c in sheet.counties.all() for s in c.services.all()] + list(sheet.cities.all())
            total = len(all_rows)
            complete = sum(1 for row in all_rows if row.state == "complete")
            production_percent = round((complete / total) * 100) if total else 0
        else:
            total = 0
            complete = 0
            production_percent = 0
        overall_parts = [technical_progress["percent"]]
        if sheet:
            overall_parts.append(production_percent)
        overall_percent = round(sum(overall_parts) / len(overall_parts)) if overall_parts else 0
        area_plans = [
            item.plan for item in project.contracted_plans.all()
            if item.is_active and item.plan.department == PlanDepartment.DEVELOPMENT
        ]
        workflow_plans = [item.plan for item in project.contracted_plans.all() if item.is_active]
        rows.append({
            "project": project,
            "questionnaire": questionnaire,
            "questionnaire_done": bool(questionnaire and questionnaire.status == QuestionnaireStatus.COMPLETE),
            "technical_progress": technical_progress,
            "sheet": sheet,
            "production_total": total,
            "production_complete": complete,
            "production_percent": production_percent,
            "overall_percent": overall_percent,
            "last_log": last_log,
            "area_plans": area_plans,
            "workflow_plans": workflow_plans,
        })
    return render(request, "questionnaires/development_dashboard.html", {"rows": rows})


@role_required("developer")
def create_for_project(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not can_access_project(request.user, project):
        raise PermissionDenied("Este proyecto no está asignado a Desarrollo.")

    if request.method == "GET" and request.GET.get("auto") == "1":
        template = QuestionnaireTemplate.objects.filter(project_type=project.project_type, is_active=True).order_by("id").first()
        if not template and project.project_type == "seo":
            template = QuestionnaireTemplate.objects.filter(project_type="website", is_active=True).order_by("id").first()
        if template:
            obj, _ = ProjectQuestionnaire.objects.get_or_create(
                project=project,
                template=template,
                defaults={"created_by": request.user, "status": QuestionnaireStatus.DRAFT},
            )
            log_activity(request.user, "questionnaires", "create", obj)
            return redirect("questionnaires:fill", pk=obj.pk)

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
        .prefetch_related("template__sections__questions", "answers__question", "answers__updated_by"),
        pk=pk,
    )
    if not can_access_project(request.user, questionnaire.project):
        raise PermissionDenied("Este proyecto no está asignado a Desarrollo.")

    if questionnaire.template.code == WEBSITE_TEMPLATE_CODE:
        if request.method == "POST":
            with transaction.atomic():
                progress = _website_save(questionnaire, request)
                log_activity(
                    request.user, "questionnaires", "save_website_technical", questionnaire,
                    description=f"Ficha técnica {progress['percent']}%",
                )
            messages.success(request, f"Ficha técnica guardada · {progress['percent']}% completado.")
            return redirect("questionnaires:fill", pk=pk)
        return render(request, "questionnaires/website_fill.html", _website_fill_context(questionnaire))

    # Generic questionnaire remains available for software/other project types.
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
            log_activity(request.user, "questionnaires", "save_answers", questionnaire)
        messages.success(request, "Ficha técnica guardada.")
        if questionnaire.status == QuestionnaireStatus.COMPLETE:
            return redirect("questionnaires:development_dashboard")
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
