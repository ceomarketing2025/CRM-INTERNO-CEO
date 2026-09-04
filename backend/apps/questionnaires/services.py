from django.db import transaction
from django.utils import timezone
from .models import Answer, ProjectQuestionnaire
from .models.choices import AnswerState, QuestionnaireStatus

WEBSITE_TEMPLATE_CODE = "website-technical-v2"

# Internal notes do not block completion.
WEBSITE_PROGRESS_KEYS = [
    "company_description",
    "slogan",
    "has_mission_vision",
    "show_team",
    "main_services",
    "service_areas",
    "coverage",
    "future_expansion",
    "seo_page_strategy",
    "business_hours",
    "is_24_7",
    "contact_numbers",
    "has_social",
    "has_webmail",
    "has_gbp",
    "has_website",
    "certifications",
    "warranties",
    "experience_years",
]


def _question_map(questionnaire):
    return {
        question.key: question
        for section in questionnaire.template.sections.prefetch_related("questions").all()
        for question in section.questions.all()
    }


def _answer_map(questionnaire):
    return {answer.question.key: answer for answer in questionnaire.answers.select_related("question", "updated_by")}


def save_key_answer(*, questionnaire, key, user, value_text="", value_json=None, complete=False, negative=False):
    question = _question_map(questionnaire).get(key)
    if not question:
        return None
    state = AnswerState.NO if negative and complete else (AnswerState.CONFIRMED if complete else AnswerState.PENDING)
    answer, _ = Answer.objects.update_or_create(
        questionnaire=questionnaire,
        question=question,
        defaults={
            "state": state,
            "value_text": value_text or "",
            "value_json": value_json or {},
            "updated_by": user,
        },
    )
    return answer


def website_answer_payload(questionnaire):
    # Always expose every field expected by the dedicated website template.
    # This keeps brand-new questionnaires safe: templates can read
    # data.<key>.text/json/complete without VariableDoesNotExist.
    known_keys = list(dict.fromkeys(WEBSITE_PROGRESS_KEYS + ["internal_meeting_notes"]))
    result = {
        key: {
            "text": "",
            "json": {},
            "complete": False,
            "state": AnswerState.PENDING,
            "updated_by": None,
            "updated_at": None,
        }
        for key in known_keys
    }
    for key, answer in _answer_map(questionnaire).items():
        result[key] = {
            "text": answer.value_text or "",
            "json": answer.value_json or {},
            "complete": answer.state in {AnswerState.CONFIRMED, AnswerState.NO, AnswerState.NOT_APPLICABLE},
            "state": answer.state,
            "updated_by": answer.updated_by,
            "updated_at": answer.updated_at,
        }
    return result


def website_questionnaire_progress(questionnaire):
    if not questionnaire or questionnaire.template.code != WEBSITE_TEMPLATE_CODE:
        return {"complete": 0, "total": 0, "percent": 0}
    answers = _answer_map(questionnaire)
    completed = sum(
        1 for key in WEBSITE_PROGRESS_KEYS
        if key in answers and answers[key].state in {AnswerState.CONFIRMED, AnswerState.NO, AnswerState.NOT_APPLICABLE}
    )
    total = len(WEBSITE_PROGRESS_KEYS)
    return {"complete": completed, "total": total, "percent": round((completed / total) * 100) if total else 0}


def _join_services(items):
    return "\n".join(item.get("name", "").strip() for item in items if item.get("name", "").strip() and not item.get("excluded"))


def _join_areas(items):
    rows = []
    for item in items:
        name = item.get("name", "").strip()
        if not name:
            continue
        label = {"state": "Estado", "county": "Condado", "city": "Ciudad"}.get(item.get("type"), "Área")
        rows.append(f"{label}: {name}")
    return "\n".join(rows)


def _social_lines(data):
    labels = {
        "facebook": "Facebook", "instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube",
        "twitter": "X / Twitter", "yelp": "Yelp", "linkedin": "LinkedIn", "nextdoor": "Nextdoor",
    }
    lines = []
    for key, url in (data.get("networks") or {}).items():
        if str(url).strip():
            lines.append(f"{labels.get(key, key.title())}: {str(url).strip()}")
    for item in data.get("custom") or []:
        name, url = str(item.get("name", "")).strip(), str(item.get("url", "")).strip()
        if name or url:
            lines.append(f"{name or 'Otra red'}: {url}")
    return "\n".join(lines)


@transaction.atomic
def sync_website_shared_to_marketing(questionnaire, user):
    """Sync only the fields explicitly shared between Desarrollo and Marketing."""
    if questionnaire.template.code != WEBSITE_TEMPLATE_CODE:
        return None
    from apps.marketing.services import ensure_workspace, sync_workspace_checks

    workspace = ensure_workspace(questionnaire.project)
    answers = website_answer_payload(questionnaire)

    webmail = answers.get("has_webmail", {}).get("json", {})
    workspace.webmail_has = webmail.get("has", "") if webmail.get("has") in {"yes", "no"} else ""
    workspace.webmail_email = webmail.get("email", "") if workspace.webmail_has == "yes" else ""
    workspace.webmail_secure_reference_url = webmail.get("secure_reference_url", "") if workspace.webmail_has == "yes" else ""

    gbp = answers.get("has_gbp", {}).get("json", {})
    workspace.business_profile_mode = gbp.get("mode", "") if gbp.get("mode") in {"existing", "create", "no"} else ""
    workspace.business_profile_link = gbp.get("link", "") if workspace.business_profile_mode == "existing" else ""

    website = answers.get("has_website", {}).get("json", {})
    workspace.website_has = website.get("has", "") if website.get("has") in {"yes", "no"} else ""
    workspace.website_url = website.get("url", "") if workspace.website_has == "yes" else ""

    workspace.shared_info_updated_by = user
    workspace.shared_info_updated_at = timezone.now()
    workspace.save(update_fields=[
        "webmail_has", "webmail_email", "webmail_secure_reference_url", "business_profile_mode",
        "business_profile_link", "website_has", "website_url", "shared_info_updated_by", "shared_info_updated_at", "updated_at",
    ])
    sync_workspace_checks(workspace)
    return workspace


@transaction.atomic
def sync_marketing_shared_to_website(workspace, user):
    questionnaire = ProjectQuestionnaire.objects.filter(
        project=workspace.project,
        template__code=WEBSITE_TEMPLATE_CODE,
    ).select_related("template").prefetch_related("template__sections__questions", "answers__question").first()
    if not questionnaire:
        return None

    if workspace.webmail_has in {"yes", "no"}:
        webmail_credential_ready = workspace.project.project_credentials.filter(credential_type="webmail", enabled=True).exists()
        webmail_complete = workspace.webmail_has == "no" or bool(workspace.webmail_email) or webmail_credential_ready
        save_key_answer(
            questionnaire=questionnaire,
            key="has_webmail",
            user=user,
            value_text=(workspace.webmail_email or "Webmail configurado") if workspace.webmail_has == "yes" else "No cuenta con webmail",
            value_json={
                "has": workspace.webmail_has,
                "email": workspace.webmail_email or "",
                "secure_reference_url": workspace.webmail_secure_reference_url or "",
                "credential_ready": webmail_credential_ready,
            },
            complete=webmail_complete,
            negative=workspace.webmail_has == "no",
        )

    mode = workspace.business_profile_mode or ""
    if mode in {"existing", "create", "no"}:
        credential_ready = workspace.project.project_credentials.filter(credential_type="google_business", enabled=True).exists()
        save_key_answer(
            questionnaire=questionnaire,
            key="has_gbp",
            user=user,
            value_text={"existing": "Ya tiene Google Business", "create": "Crear Google Business", "no": "No tiene / no crear"}.get(mode, mode),
            value_json={"mode": mode, "link": workspace.business_profile_link or "", "notes": "", "credential_ready": credential_ready},
            complete=(mode in {"create", "no"} or (mode == "existing" and (bool(workspace.business_profile_link) or credential_ready))),
            negative=mode == "no",
        )

    if workspace.website_has in {"yes", "no"}:
        website_complete = workspace.website_has == "no" or bool(workspace.website_url)
        save_key_answer(
            questionnaire=questionnaire,
            key="has_website",
            user=user,
            value_text=workspace.website_url if workspace.website_has == "yes" else "No tiene sitio web",
            value_json={"has": workspace.website_has, "url": workspace.website_url or ""},
            complete=website_complete,
            negative=workspace.website_has == "no",
        )

    progress = website_questionnaire_progress(questionnaire)
    questionnaire.status = QuestionnaireStatus.COMPLETE if progress["percent"] == 100 else QuestionnaireStatus.IN_PROGRESS
    questionnaire.save(update_fields=["status", "updated_at"])
    return questionnaire
