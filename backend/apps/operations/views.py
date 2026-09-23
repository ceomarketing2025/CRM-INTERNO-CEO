import re
import unicodedata
from collections import defaultdict
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.utils.text import slugify
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from apps.accounts.models import UserAccount
from apps.audit.services import log_activity
from apps.clients.models import Client
from apps.core.decorators import manager_required, role_required
from apps.design.models import ColorPalette, PaletteColor
from apps.projects.models import Project
from apps.projects.selectors import can_access_project
from apps.questionnaires.models import ProjectQuestionnaire
from apps.questionnaires.services import WEBSITE_TEMPLATE_CODE, website_answer_payload
from .tasks import send_development_task_email
from .forms import DomainHostingRecordForm, ProductionRecordForm, ProjectCredentialForm, WebProductionStructureForm
from .models import (
    CompleteStatus,
    DEFAULT_TYPOGRAPHY_CONFIG,
    CredentialType,
    DomainHostingRecord,
    DomainOperationType,
    DomainRecordStatus,
    ProductionRecord,
    ProductionWorkStatus,
    ProjectCredential,
    WebProductionCounty,
    WebProductionCountyService,
    WebProductionCity,
    WebProductionInternalSection,
    WebProductionPage,
    WebProductionSheet,
    WebProductionHistory,
    WebProductionNotification,
    DevelopmentTaskNotification,
)
from .services import (
    apply_seo_automation,
    auto_workload,
    create_custom_project_credential,
    ensure_web_production_structure,
    save_domain_hosting_record,
    save_production_record,
    save_project_credential,
    upsert_project_credential,
)


@login_required
def projects_for_client(request):
    client_id = request.GET.get("client", "").strip()
    if not client_id.isdigit():
        return JsonResponse({"projects": []})
    projects = Project.objects.filter(client_id=int(client_id)).order_by("-created_at")
    if getattr(request.user, "role", "") == "sales":
        projects = projects.none()
    return JsonResponse({"projects": [
        {"id": row.pk, "label": f"{row.project_code} · {row.name}"}
        for row in projects[:100]
    ]})


@manager_required
def general_list(request):
    q = request.GET.get("q", "").strip()
    base_records = DomainHostingRecord.objects.select_related("client", "project", "updated_by")
    if q:
        base_records = base_records.filter(
            Q(client__business_name__icontains=q)
            | Q(client__first_name__icontains=q)
            | Q(client__last_name__icontains=q)
            | Q(project__name__icontains=q)
            | Q(domain_name__icontains=q)
            | Q(server_provider_other__icontains=q)
        )
    records = list(base_records[:300])
    complete = sum(1 for row in records if row.is_domain_complete)
    pending_purchase = sum(1 for row in records if row.domain_status in {DomainRecordStatus.PENDING_PURCHASE, DomainRecordStatus.LEGACY_PENDING} and row.operation_type != DomainOperationType.MIGRATION)
    pending_migration = sum(1 for row in records if row.domain_status == DomainRecordStatus.PENDING_MIGRATION or (row.operation_type == DomainOperationType.MIGRATION and row.domain_status == DomainRecordStatus.LEGACY_PENDING))
    stats = {
        "total": len(records),
        "complete": complete,
        "pending_purchase": pending_purchase,
        "pending_migration": pending_migration,
        "percent": round((complete / len(records)) * 100) if records else 0,
    }
    return render(request, "operations/general_list.html", {"records": records, "q": q, "stats": stats})


def _domain_form_context(form, title, subtitle, record=None):
    selected_operation = form.data.get("operation_type") if form.is_bound else (getattr(record, "operation_type", None) or form.initial.get("operation_type") or DomainOperationType.NEW)
    selected_operation = str(selected_operation)
    return {
        "form": form,
        "title": title,
        "subtitle": subtitle,
        "record": record,
        "operation_choices": [
            (DomainOperationType.NEW.value, "Nuevo dominio", "Compra y registro de un dominio nuevo."),
            (DomainOperationType.EXISTING.value, "Dominio existente", "El cliente ya tiene el dominio registrado."),
            (DomainOperationType.MIGRATION.value, "Migración", "El dominio se trasladará o ya fue trasladado."),
        ],
        "selected_operation": selected_operation,
    }


@manager_required
def general_create(request):
    initial = {"operation_type": DomainOperationType.NEW, "domain_status": DomainRecordStatus.PENDING_PURCHASE}
    if request.GET.get("client", "").isdigit():
        initial["client"] = request.GET["client"]
    if request.GET.get("project", "").isdigit():
        initial["project"] = request.GET["project"]
    form = DomainHostingRecordForm(request.POST or None, initial=initial, user=request.user)
    if request.method == "POST" and form.is_valid():
        save_domain_hosting_record(form=form, user=request.user)
        messages.success(request, "Dominio / hosting guardado. Servidor y WordPress quedaron sincronizados en Credenciales.")
        return redirect("operations:general_list")
    return render(request, "operations/domain_hosting_form.html", _domain_form_context(
        form, "Registrar dominio y hosting", "Selecciona cliente y luego únicamente uno de sus proyectos."
    ))


@manager_required
def general_edit(request, pk):
    obj = get_object_or_404(DomainHostingRecord, pk=pk)
    form = DomainHostingRecordForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        save_domain_hosting_record(form=form, user=request.user)
        messages.success(request, "Dominio / hosting actualizado y sincronizado.")
        return redirect("operations:general_list")
    return render(request, "operations/domain_hosting_form.html", _domain_form_context(
        form, "Editar dominio y hosting", f"{obj.client.full_name or 'Sin nombre'} · {obj.client.business_name} · {obj.project.name}", obj
    ))


@manager_required
def general_detail(request, pk):
    obj = get_object_or_404(DomainHostingRecord.objects.select_related("client", "project", "created_by", "updated_by"), pk=pk)
    return render(request, "operations/general_detail.html", {"record": obj})


@manager_required
@require_POST
def general_quick_status(request, pk):
    obj = get_object_or_404(DomainHostingRecord, pk=pk)
    status = request.POST.get("domain_status", "").strip()
    allowed = set(obj.allowed_statuses)
    if status not in allowed:
        messages.error(request, "Ese estado no corresponde al tipo de dominio seleccionado.")
        return redirect("operations:general_list")
    obj.domain_status = status
    obj.updated_by = request.user
    obj.full_clean()
    obj.save()
    log_activity(request.user, "operations", "domain_status", obj, obj.project_domain_label)
    messages.success(request, f"{obj.domain_name or obj.project.name}: {obj.project_domain_label}.")
    return redirect(request.POST.get("next") or "operations:general_list")


@manager_required
@require_POST
def general_delete(request, pk):
    obj = get_object_or_404(DomainHostingRecord, pk=pk)
    label = obj.domain_name or obj.project.name
    log_activity(request.user, "operations", "domain_hosting_delete", obj, description=f"Eliminado {label}")
    obj.delete()
    messages.success(request, "Registro de dominio / hosting eliminado.")
    return redirect("operations:general_list")


@manager_required
def credential_list(request):
    q = request.GET.get("q", "").strip()
    records = ProjectCredential.objects.select_related("client", "project", "updated_by")
    if q:
        records = records.filter(
            Q(client__business_name__icontains=q)
            | Q(project__name__icontains=q)
            | Q(account_email__icontains=q)
            | Q(custom_name__icontains=q)
        )
    return render(request, "operations/credential_list.html", {"records": records[:400], "q": q})


FIXED_CREDENTIAL_TYPES = [
    (CredentialType.GOOGLE, "Google / Gmail", "Un solo acceso para el ecosistema Google: Gmail, Business, Ads, etc."),
    (CredentialType.SERVER, "Servidor", "Hosting o servidor del proyecto."),
    (CredentialType.WORDPRESS, "WordPress", "Acceso administrador del sitio."),
    (CredentialType.META, "Meta", "Facebook / Meta Business."),
    (CredentialType.YOUTUBE, "YouTube", "Canal o cuenta de YouTube."),
    (CredentialType.TIKTOK, "TikTok", "Cuenta de TikTok."),
]


def _credential_record_for_group(project, code):
    exact = ProjectCredential.objects.filter(project=project, credential_type=code).order_by("id").first()
    if exact:
        return exact
    legacy_map = {
        CredentialType.GOOGLE: [CredentialType.GOOGLE_BUSINESS, CredentialType.GOOGLE_ADS, CredentialType.GOOGLE_LSA, CredentialType.SEARCH_CONSOLE, CredentialType.ANALYTICS],
        CredentialType.SERVER: [CredentialType.SITEGROUND],
    }
    legacy_types = legacy_map.get(code, [])
    return ProjectCredential.objects.filter(project=project, credential_type__in=legacy_types, enabled=True).order_by("-updated_at").first() if legacy_types else None


@manager_required
def credential_snapshot(request):
    project_id = request.GET.get("project", "").strip()
    if not project_id.isdigit():
        return JsonResponse({"fixed": {}, "others": [], "provider": ""})
    project = get_object_or_404(Project.objects.select_related("client"), pk=int(project_id))
    domain = project.domain_hosting_records.order_by("-updated_at").first()
    fixed = {}
    for code, _label, _help in FIXED_CREDENTIAL_TYPES:
        row = _credential_record_for_group(project, code)
        if not row:
            inferred = bool(domain and code in {CredentialType.SERVER, CredentialType.WORDPRESS})
            fixed[code] = {"enabled": inferred, "account": "", "login": "", "notes": "", "visible": False, "has_password": False, "custom_name": domain.provider_label if inferred and code == CredentialType.SERVER else ""}
            continue
        fixed[code] = {
            "id": row.pk,
            "enabled": row.enabled,
            "account": row.account_email,
            "login": row.login_url,
            "notes": row.notes,
            "visible": row.visible_to_team,
            "has_password": bool(row.password_encrypted),
            "custom_name": row.custom_name,
        }
    others = [
        {
            "id": row.pk, "name": row.display_name, "account": row.account_email,
            "visible": row.visible_to_team, "enabled": row.enabled,
            "edit_url": reverse("operations:credential_edit", args=[row.pk]),
        }
        for row in ProjectCredential.objects.filter(project=project, credential_type=CredentialType.OTHER).order_by("custom_name", "id")
    ]
    return JsonResponse({
        "fixed": fixed,
        "others": others,
        "provider": domain.provider_label if domain else "",
        "client": f"{project.client.full_name or 'Sin nombre'} · {project.client.business_name}",
    })


@manager_required
def credential_create(request):
    initial_client = request.GET.get("client", "")
    initial_project = request.GET.get("project", "")
    selected_client = request.POST.get("client", initial_client)
    selected_project = request.POST.get("project", initial_project)
    project_options = Project.objects.filter(client_id=selected_client).order_by("-created_at") if str(selected_client).isdigit() else Project.objects.none()

    if request.method == "POST":
        client = Client.objects.filter(pk=selected_client).first() if str(selected_client).isdigit() else None
        project = Project.objects.filter(pk=selected_project).first() if str(selected_project).isdigit() else None
        selected = set(request.POST.getlist("credential_types"))
        errors = []
        if not client:
            errors.append("Selecciona un cliente.")
        if not project or (client and project.client_id != client.pk):
            errors.append("Selecciona un proyecto perteneciente al cliente.")

        if not errors:
            saved = 0
            for code, _label, _help in FIXED_CREDENTIAL_TYPES:
                existing = ProjectCredential.objects.filter(project=project, credential_type=code).order_by("id").first()
                grouped_existing = _credential_record_for_group(project, code)
                if code not in selected:
                    if existing and existing.enabled:
                        existing.enabled = False
                        existing.updated_by = request.user
                        existing.save(update_fields=["enabled", "updated_by", "updated_at"])
                    continue

                # Si el proyecto venía de V10 con Google Business/SiteGround separados,
                # reutilizamos ese registro para conservar la contraseña cifrada.
                if existing is None and grouped_existing is not None and grouped_existing.credential_type != code:
                    grouped_existing.credential_type = code
                    grouped_existing.updated_by = request.user
                    grouped_existing.save(update_fields=["credential_type", "updated_by", "updated_at"])

                provider_name = ""
                if code == CredentialType.SERVER:
                    latest_domain = project.domain_hosting_records.order_by("-updated_at").first()
                    provider_name = latest_domain.provider_label if latest_domain else ""
                upsert_project_credential(
                    client=client,
                    project=project,
                    credential_type=code,
                    user=request.user,
                    account_email=request.POST.get(f"account_{code}", "").strip(),
                    password=request.POST.get(f"password_{code}", ""),
                    login_url=request.POST.get(f"login_{code}", "").strip(),
                    custom_name=provider_name,
                    visible_to_team=request.POST.get(f"visible_{code}") == "1",
                    enabled=True,
                    notes=request.POST.get(f"notes_{code}", "").strip(),
                )
                saved += 1

            other_names = request.POST.getlist("other_name")
            other_accounts = request.POST.getlist("other_account")
            other_passwords = request.POST.getlist("other_password")
            other_logins = request.POST.getlist("other_login")
            other_notes = request.POST.getlist("other_notes")
            other_visible = set(request.POST.getlist("other_visible"))
            for index, name in enumerate(other_names):
                name = name.strip()
                if not name:
                    continue
                create_custom_project_credential(
                    client=client, project=project, user=request.user, custom_name=name,
                    account_email=other_accounts[index] if index < len(other_accounts) else "",
                    password=other_passwords[index] if index < len(other_passwords) else "",
                    login_url=other_logins[index] if index < len(other_logins) else "",
                    notes=other_notes[index] if index < len(other_notes) else "",
                    visible_to_team=str(index) in other_visible,
                )
                saved += 1

            messages.success(request, f"{saved} acceso(s) guardados. Los cambios compartidos quedaron sincronizados.")
            return redirect("operations:credential_list")

        for error in errors:
            messages.error(request, error)

    return render(request, "operations/credential_bulk_form.html", {
        "credential_types": FIXED_CREDENTIAL_TYPES,
        "clients": Client.objects.order_by("first_name", "last_name", "business_name"),
        "project_options": project_options,
        "selected_client": str(selected_client or ""),
        "selected_project": str(selected_project or ""),
    })


@manager_required
def credential_edit(request, pk):
    obj = get_object_or_404(ProjectCredential, pk=pk)
    form = ProjectCredentialForm(request.POST or None, instance=obj, user=request.user)
    if request.method == "POST" and form.is_valid():
        save_project_credential(form=form, user=request.user)
        messages.success(request, "Credencial actualizada.")
        return redirect("operations:credential_list")
    return render(request, "operations/credential_form.html", {
        "form": form,
        "title": "Editar credencial",
        "subtitle": f"{obj.client.business_name} · {obj.project.name}",
        "record": obj,
    })


@login_required
def credential_detail(request, pk):
    obj = get_object_or_404(ProjectCredential.objects.select_related("client", "project", "created_by", "updated_by"), pk=pk)
    can_reveal = bool(request.user.is_manager or (obj.enabled and obj.visible_to_team))
    if not can_reveal:
        raise PermissionDenied("Gerencia no ha habilitado esta credencial para el equipo.")
    return render(request, "operations/credential_detail.html", {
        "record": obj,
        "can_reveal": True,
        "password_value": obj.get_password(),
    })


@manager_required
@require_POST
def credential_delete(request, pk):
    obj = get_object_or_404(ProjectCredential, pk=pk)
    label = obj.display_name
    log_activity(request.user, "operations", "credential_delete", obj, description=f"Eliminada {label}")
    obj.delete()
    messages.success(request, "Credencial eliminada.")
    return redirect("operations:credential_list")


@manager_required
def production_list(request):
    records = ProductionRecord.objects.select_related("client", "project", "collaborator")
    return render(request, "operations/production_list.html", {"records": records})


@manager_required
def production_create(request):
    form = ProductionRecordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        save_production_record(form=form, user=request.user); messages.success(request, "Registro de producción guardado."); return redirect("operations:production_list")
    return render(request, "shared/form.html", {"form": form, "title": "Nuevo registro · Producción", "subtitle": "Plan, diseño, estado técnico, colaborador y valores."})


@manager_required
def production_edit(request, pk):
    obj = get_object_or_404(ProductionRecord, pk=pk)
    form = ProductionRecordForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        save_production_record(form=form, user=request.user); messages.success(request, "Producción actualizada."); return redirect("operations:production_list")
    return render(request, "shared/form.html", {"form": form, "title": "Editar producción", "subtitle": obj.client.business_name})


# ---------------------------------------------------------------------------
# DESARROLLO · FICHA DE PRODUCCIÓN WEB · V5
# ---------------------------------------------------------------------------


def _developer_users():
    return UserAccount.objects.filter(
        role__in=[
            UserAccount.Role.DEVELOPER,
            UserAccount.Role.MANAGER,
        ],
        is_active=True,
    ).order_by(
        "first_name",
        "last_name",
        "email",
    )


def _technical_production_inputs(project):
    questionnaire = (
        ProjectQuestionnaire.objects
        .filter(
            project=project,
            template__code=WEBSITE_TEMPLATE_CODE,
        )
        .prefetch_related(
            "answers__question"
        )
        .first()
    )

    services = []
    strategy = ""

    if questionnaire:
        for answer in questionnaire.answers.all():

            if answer.question.key == "main_services":
                services = [
                    item
                    for item in (
                        answer.value_json
                        or {}
                    ).get(
                        "items",
                        [],
                    )
                    if (
                        item.get("name")
                        and not item.get("excluded")
                    )
                ]

            elif (
                answer.question.key
                == "seo_page_strategy"
            ):
                strategy = (
                    answer.value_json
                    or {}
                ).get(
                    "strategy",
                    "",
                )

    seen = set()
    normalized = []

    for item in sorted(
        services,
        key=lambda x: (
            not bool(
                x.get("primary")
            ),
            str(
                x.get(
                    "name",
                    "",
                )
            ).lower(),
        ),
    ):
        name = str(
            item.get(
                "name",
                "",
            )
        ).strip()

        key = name.lower()

        if (
            name
            and key not in seen
        ):
            seen.add(key)

            normalized.append(
                {
                    "name": name,
                    "primary": bool(
                        item.get(
                            "primary"
                        )
                    ),
                }
            )

    return (
        questionnaire,
        normalized,
        strategy,
    )



_PROJECT_FULL_ACCESS_RESPONSIBILITIES = {
    "responsable",
    "responsable proyecto",
    "responsable del proyecto",
    "responsable principal",
    "admin",
    "admin proyecto",
    "admin del proyecto",
    "administrador",
    "administrador proyecto",
    "administrador del proyecto",
}


def _normalized_responsibility(value):
    normalized = unicodedata.normalize(
        "NFKD",
        str(value or ""),
    )
    normalized = "".join(
        char
        for char in normalized
        if not unicodedata.combining(char)
    )
    return " ".join(
        normalized.lower().strip().split()
    )


def _can_manage_full_development_project(user, project):
    if (
        getattr(user, "is_superuser", False)
        or getattr(user, "is_manager", False)
    ):
        return True

    assignments = project.assignments.filter(
        user=user,
        area="development",
        status__in=["assigned", "active"],
    ).only("responsibility")

    return any(
        _normalized_responsibility(assignment.responsibility)
        in _PROJECT_FULL_ACCESS_RESPONSIBILITIES
        for assignment in assignments
    )


def _can_edit_production_row(user, obj, can_manage_project=False):
    user_id = getattr(user, "pk", None)
    responsible_id = getattr(obj, "responsible_id", None)

    if getattr(user, "is_superuser", False) or getattr(user, "is_manager", False):
        return True

    # El responsable principal mantiene acceso total sobre filas ajenas, pero si
    # también es el responsable de esta fila debe respetar el bloqueo de revisión.
    if can_manage_project and responsible_id != user_id:
        return True

    if responsible_id != user_id:
        return False

    return getattr(obj, "workflow_status", None) not in {
        ProductionWorkStatus.IN_REVIEW,
        ProductionWorkStatus.COMPLETE,
    }


def _can_force_complete_production_row(user):
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "is_manager", False)
    )


def _can_review_production_row(user, obj, can_manage_project=False):
    user_id = getattr(user, "pk", None)

    # Gerencia Global / superuser puede intervenir en cualquier revisión.
    if getattr(user, "is_superuser", False) or getattr(user, "is_manager", False):
        return True

    # Nadie que figure como responsable del trabajo puede auto-revisarse,
    # incluso si además es el responsable principal del proyecto.
    if getattr(obj, "responsible_id", None) == user_id:
        return False

    # Fuera de Gerencia, la revisión pertenece exclusivamente al revisor asignado.
    return bool(
        getattr(obj, "reviewer_id", None) == user_id
    )


def _require_production_row_edit(user, obj, can_manage_project=False):
    if not _can_edit_production_row(
        user,
        obj,
        can_manage_project=can_manage_project,
    ):
        raise PermissionDenied(
            "Solo el responsable asignado puede modificar este elemento."
        )


def _require_project_production_admin(can_manage_project):
    if not can_manage_project:
        raise PermissionDenied(
            "Solo el responsable o admin del proyecto puede modificar esta configuración."
        )


def _binary(value):
    return (
        CompleteStatus.COMPLETE
        if value
        == CompleteStatus.COMPLETE
        else CompleteStatus.INCOMPLETE
    )


def _sync_legacy_production_flags(obj):
    """Keep legacy state/review fields aligned with the workflow source of truth."""
    workflow_status = getattr(obj, "workflow_status", None)
    is_complete = workflow_status == ProductionWorkStatus.COMPLETE

    if hasattr(obj, "state"):
        obj.state = (
            CompleteStatus.COMPLETE
            if is_complete
            else CompleteStatus.INCOMPLETE
        )

    if hasattr(obj, "review_status"):
        obj.review_status = (
            CompleteStatus.COMPLETE
            if is_complete
            else CompleteStatus.INCOMPLETE
        )


def _production_history_snapshot(obj):
    return {
        "workflow_status": getattr(obj, "workflow_status", "") or "",
        "review_status": getattr(obj, "review_status", "") or "",
        "responsible_id": getattr(obj, "responsible_id", None),
        "reviewer_id": getattr(obj, "reviewer_id", None),
    }


def _production_history_label(obj):
    return (
        getattr(obj, "name", "")
        or getattr(obj, "service_name", "")
        or f"Elemento {getattr(obj, 'pk', '')}"
    )


def _record_production_history(sheet, obj, row_type, user, event, from_status="", to_status="", note=""):
    WebProductionHistory.objects.create(
        sheet=sheet,
        row_type=row_type,
        row_id=obj.pk,
        row_label=_production_history_label(obj),
        event=event,
        from_status=from_status or "",
        to_status=to_status or "",
        note=(note or "").strip(),
        actor=user,
    )


def _create_production_notification(sheet, obj, row_type, actor, recipient, event, message):
    if not recipient or recipient.pk == getattr(actor, "pk", None):
        return
    WebProductionNotification.objects.create(
        sheet=sheet,
        recipient=recipient,
        actor=actor,
        row_type=row_type,
        row_id=obj.pk,
        row_label=_production_history_label(obj),
        event=event,
        message=(message or "").strip(),
    )


def _notify_production_transition(sheet, obj, row_type, actor, old_status, new_status, review_note=""):
    label = _production_history_label(obj)
    if new_status == ProductionWorkStatus.IN_REVIEW:
        _create_production_notification(
            sheet, obj, row_type, actor, getattr(obj, "reviewer", None),
            "sent_to_review",
            f"{label} fue enviado a revisión.",
        )
    elif old_status == ProductionWorkStatus.IN_REVIEW and new_status == ProductionWorkStatus.IN_PROGRESS:
        detail = f" Observación: {review_note}" if review_note else ""
        _create_production_notification(
            sheet, obj, row_type, actor, getattr(obj, "responsible", None),
            "review_returned",
            f"{label} requiere cambios.{detail}",
        )
    elif new_status == ProductionWorkStatus.COMPLETE:
        _create_production_notification(
            sheet, obj, row_type, actor, getattr(obj, "responsible", None),
            "review_approved",
            f"{label} fue aprobado y quedó completo.",
        )


def _record_production_changes(sheet, obj, row_type, user, before, review_note=""):
    after = _production_history_snapshot(obj)
    created = False

    if before.get("responsible_id") != after.get("responsible_id"):
        _record_production_history(
            sheet, obj, row_type, user, "responsible_changed",
            note="Responsable actualizado.",
        )
        created = True

    if before.get("reviewer_id") != after.get("reviewer_id"):
        _record_production_history(
            sheet, obj, row_type, user, "reviewer_changed",
            note="Revisor actualizado.",
        )
        created = True

    old_status = before.get("workflow_status") or ""
    new_status = after.get("workflow_status") or ""
    if old_status != new_status:
        if new_status == ProductionWorkStatus.IN_REVIEW:
            event = "sent_to_review"
        elif old_status == ProductionWorkStatus.IN_REVIEW and new_status == ProductionWorkStatus.IN_PROGRESS:
            event = "review_returned"
        elif new_status == ProductionWorkStatus.COMPLETE:
            event = "review_approved"
        else:
            event = "status_changed"
        _record_production_history(
            sheet, obj, row_type, user, event,
            from_status=old_status,
            to_status=new_status,
            note=review_note,
        )
        _notify_production_transition(
            sheet, obj, row_type, user, old_status, new_status,
            review_note=review_note,
        )
        created = True

    if not created:
        _record_production_history(
            sheet, obj, row_type, user, "content_updated",
            from_status=after.get("workflow_status", ""),
            to_status=after.get("workflow_status", ""),
        )


def _update_seo_row(
    obj,
    request,
    prefix,
    allowed_responsibles,
    allowed_reviewers,
    allow_assignment_changes=True,
    allow_structure_changes=True,
    allow_complete=True,
    allow_review_status=True,
    sheet=None,
    row_type="",
):
    history_before = _production_history_snapshot(obj)

    if allow_structure_changes:
        obj.name = request.POST.get(
            f"{prefix}_name",
            obj.name,
        ).strip()

    obj.keyword = request.POST.get(
        f"{prefix}_keyword",
        "",
    ).strip()

    posted_slug = request.POST.get(
        f"{prefix}_slug",
        "",
    ).strip()

    if posted_slug:
        obj.slug = posted_slug

    obj.secondary_keywords = (
        request.POST.get(
            f"{prefix}_secondary_keywords",
            "",
        ).strip()
    )

    obj.meta_title = request.POST.get(
        f"{prefix}_meta_title",
        "",
    ).strip()

    obj.meta_description = (
        request.POST.get(
            f"{prefix}_meta_description",
            "",
        ).strip()
    )

    obj.notes = request.POST.get(
        f"{prefix}_notes",
        "",
    ).strip()

    review_status = request.POST.get(
        f"{prefix}_review_status",
        "",
    )

    if review_status and allow_review_status:
        obj.review_status = _binary(
            review_status
        )

    workflow_status = request.POST.get(
        f"{prefix}_workflow_status",
        "",
    )

    if (
        workflow_status
        == ProductionWorkStatus.COMPLETE
        and not allow_complete
    ):
        raise PermissionDenied(
            "El estado Completo no está disponible para este desarrollador."
        )

    if allow_assignment_changes:
        responsible_id = request.POST.get(
            f"{prefix}_responsible",
            "",
        ).strip()

        obj.responsible = (
            allowed_responsibles.get(
                int(responsible_id)
            )
            if responsible_id.isdigit()
            else None
        )

        reviewer_id = request.POST.get(
            f"{prefix}_reviewer",
            "",
        ).strip()

        obj.reviewer = (
            allowed_reviewers.get(
                int(reviewer_id)
            )
            if reviewer_id.isdigit()
            else None
        )

    if (
        workflow_status
        == ProductionWorkStatus.IN_REVIEW
        and not obj.reviewer_id
    ):
        messages.error(
            request,
            "Selecciona un revisor antes de enviar este elemento a revisión.",
        )
    elif (
        workflow_status
        in ProductionWorkStatus.values
    ):
        obj.workflow_status = workflow_status

    if isinstance(
        obj,
        WebProductionCountyService,
    ):
        if allow_structure_changes:
            obj.service_name = (
                request.POST.get(
                    f"{prefix}_service_name",
                    obj.service_name,
                ).strip()
            )

            obj.is_global = (
                request.POST.get(
                    f"{prefix}_is_global"
                )
                == "1"
            )

        if (
            not obj.name
            and obj.service_name
        ):
            obj.name = (
                f"{obj.service_name} "
                f"{obj.county.name}"
            ).strip()

    elif isinstance(
        obj,
        WebProductionCity,
    ) and allow_structure_changes:
        county_id = request.POST.get(
            f"{prefix}_county",
            "",
        ).strip()

        obj.county = (
            WebProductionCounty.objects
            .filter(
                pk=county_id,
                sheet=obj.sheet,
            )
            .first()
            if county_id.isdigit()
            else None
        )

    obj.updated_by = request.user
    _sync_legacy_production_flags(obj)

    apply_seo_automation(
        obj
    )

    obj.save()

    if sheet is not None and row_type:
        _record_production_changes(
            sheet, obj, row_type, request.user, history_before
        )


def _update_internal_section(
    obj,
    request,
    prefix,
    allowed_responsibles,
    allowed_reviewers,
    allow_assignment_changes=True,
    allow_structure_changes=True,
    allow_complete=True,
    sheet=None,
    row_type="internal_section",
):
    history_before = _production_history_snapshot(obj)

    if allow_structure_changes:
        obj.name = request.POST.get(
            f"{prefix}_name",
            obj.name,
        ).strip()

    if allow_assignment_changes:
        responsible_id = request.POST.get(
            f"{prefix}_responsible",
            "",
        ).strip()

        obj.responsible = (
            allowed_responsibles.get(
                int(responsible_id)
            )
            if responsible_id.isdigit()
            else None
        )

        reviewer_id = request.POST.get(
            f"{prefix}_reviewer",
            "",
        ).strip()

        obj.reviewer = (
            allowed_reviewers.get(
                int(reviewer_id)
            )
            if reviewer_id.isdigit()
            else None
        )

    workflow_status = request.POST.get(
        f"{prefix}_workflow_status",
        "",
    )

    if (
        workflow_status
        == ProductionWorkStatus.COMPLETE
        and not allow_complete
    ):
        raise PermissionDenied(
            "El estado Completo no está disponible para este desarrollador."
        )

    if (
        workflow_status
        == ProductionWorkStatus.IN_REVIEW
        and not obj.reviewer_id
    ):
        messages.error(
            request,
            "Selecciona un revisor antes de enviar esta sección a revisión.",
        )
    elif (
        workflow_status
        in ProductionWorkStatus.values
    ):
        obj.workflow_status = workflow_status

    obj.created = (
        request.POST.get(
            f"{prefix}_created"
        )
        in {
            "1",
            "true",
            "on",
            "yes",
        }
    )

    obj.notes = request.POST.get(
        f"{prefix}_notes",
        "",
    ).strip()

    if allow_assignment_changes:
        complexity = request.POST.get(f"{prefix}_complexity", "").strip()
        if complexity in {"S", "M", "C"}:
            obj.complexity = complexity
            obj.points = {"S": 1, "M": 2, "C": 3}[complexity]

    obj.smtp_email = request.POST.get(
        f"{prefix}_smtp_email",
        obj.smtp_email,
    ).strip()

    smtp_password = request.POST.get(
        f"{prefix}_smtp_password",
        "",
    )
    if smtp_password.strip():
        obj.set_smtp_password(smtp_password)

    if request.POST.get(f"{prefix}_clear_smtp_password") == "1":
        obj.smtp_password_encrypted = ""

    obj.updated_by = request.user
    _sync_legacy_production_flags(obj)
    obj.save()

    if sheet is not None and row_type:
        _record_production_changes(
            sheet, obj, row_type, request.user, history_before
        )




_STYLE_PALETTE_DEFAULTS = {
    "text": "#000000",
    "background": "#FFFFFF",
    "primary": "#0C3168",
    "secondary": "#C9CBD1",
    "accent": "#2571B7",
}
_STYLE_PALETTE_LABELS = {
    "text": "Texto",
    "background": "Fondo",
    "primary": "Primario",
    "secondary": "Secundario",
    "accent": "Acento",
}
_STYLE_PALETTE_USAGE = {
    "text": "Texto principal y contraste",
    "background": "Fondos y áreas neutras",
    "primary": "Secciones principales y llamados a la acción",
    "secondary": "Tarjetas, botones secundarios y apoyo visual",
    "accent": "Elementos clave, links y detalles",
}
_DEFAULT_HEADER_STRUCTURE = "Home | About | Services | Areas We Service | Gallery | Contact | Free Estimate"


def _style_palette_for_project(project):
    palette = project.color_palettes.filter(is_primary=True).order_by("id").first()
    if not palette:
        palette = ColorPalette.objects.create(
            project=project,
            name="Paleta principal",
            is_primary=True,
        )
    by_role = {item.role: item for item in palette.colors.all()}
    for order, (role, hex_code) in enumerate(_STYLE_PALETTE_DEFAULTS.items(), start=1):
        if role not in by_role:
            by_role[role] = PaletteColor.objects.create(
                palette=palette,
                role=role,
                label=_STYLE_PALETTE_LABELS[role],
                hex_code=hex_code,
                usage=_STYLE_PALETTE_USAGE[role],
                order=order,
            )
    return palette


def _normalized_typography_config(sheet):
    source = sheet.typography_config or {}
    result = {}
    for key, default in DEFAULT_TYPOGRAPHY_CONFIG.items():
        value = source.get(key) if isinstance(source, dict) else None
        result[key] = dict(default)
        if isinstance(value, dict):
            result[key].update({k: v for k, v in value.items() if v not in (None, "")})
    return result


@role_required("developer")
def development_project_styles(request, project_pk):
    project = get_object_or_404(
        Project.objects.select_related("client"),
        pk=project_pk,
    )
    if not can_access_project(request.user, project):
        raise PermissionDenied("No tienes acceso a este proyecto.")

    sheet, _ = WebProductionSheet.objects.get_or_create(project=project)
    if not (sheet.header_structure or "").strip():
        sheet.header_structure = _DEFAULT_HEADER_STRUCTURE
        sheet.save(update_fields=["header_structure", "updated_at"])
    can_manage_styles = _can_manage_full_development_project(request.user, project)
    palette = _style_palette_for_project(project)

    if request.method == "POST":
        if not can_manage_styles:
            raise PermissionDenied("Solo Gerencia, Admin o el Responsable principal puede modificar Estilos.")

        action = request.POST.get("action", "").strip()

        if action == "save_typography":
            config = _normalized_typography_config(sheet)
            for key in DEFAULT_TYPOGRAPHY_CONFIG:
                config[key]["font"] = request.POST.get(f"{key}_font", config[key].get("font", "")).strip() or config[key].get("font", "")
                raw_size = request.POST.get(f"{key}_size", "").strip()
                raw_weight = request.POST.get(f"{key}_weight", "").strip()
                raw_line = request.POST.get(f"{key}_line_height", "").strip()
                if raw_size.isdigit():
                    config[key]["size"] = max(8, min(140, int(raw_size)))
                if raw_weight.isdigit():
                    config[key]["weight"] = max(100, min(900, int(raw_weight)))
                if raw_line:
                    config[key]["line_height"] = raw_line[:12]
                if key == "kicker":
                    config[key]["letter_spacing"] = request.POST.get("kicker_letter_spacing", config[key].get("letter_spacing", "0.14em")).strip()[:20] or "0.14em"
            sheet.typography_config = config
            sheet.updated_by = request.user
            sheet.save(update_fields=["typography_config", "updated_by", "updated_at"])
            log_activity(request.user, "development", "styles_typography_save", sheet)
            messages.success(request, "Tipografía guardada.")

        elif action == "reset_typography":
            sheet.typography_config = {key: dict(value) for key, value in DEFAULT_TYPOGRAPHY_CONFIG.items()}
            sheet.updated_by = request.user
            sheet.save(update_fields=["typography_config", "updated_by", "updated_at"])
            log_activity(request.user, "development", "styles_typography_reset", sheet)
            messages.success(request, "Tipografía restaurada al estándar.")

        elif action == "save_header":
            sheet.header_structure = request.POST.get("header_structure", "").strip() or _DEFAULT_HEADER_STRUCTURE
            sheet.updated_by = request.user
            sheet.save(update_fields=["header_structure", "updated_by", "updated_at"])
            log_activity(request.user, "development", "styles_header_save", sheet)
            messages.success(request, "Estructura del header guardada.")

        elif action == "reset_header":
            sheet.header_structure = _DEFAULT_HEADER_STRUCTURE
            sheet.updated_by = request.user
            sheet.save(update_fields=["header_structure", "updated_by", "updated_at"])
            log_activity(request.user, "development", "styles_header_reset", sheet)
            messages.success(request, "Header restaurado al estándar.")

        elif action == "save_buttons":
            sheet.button_style_code = request.POST.get("button_style_code", "")
            sheet.updated_by = request.user
            sheet.save(update_fields=["button_style_code", "updated_by", "updated_at"])
            log_activity(request.user, "development", "styles_buttons_save", sheet)
            messages.success(request, "Estilo de botones guardado.")

        elif action == "delete_buttons":
            sheet.button_style_code = ""
            sheet.updated_by = request.user
            sheet.save(update_fields=["button_style_code", "updated_by", "updated_at"])
            log_activity(request.user, "development", "styles_buttons_delete", sheet)
            messages.success(request, "Estilo de botones eliminado.")

        elif action == "save_palette":
            valid_hex = re.compile(r"^#[0-9A-Fa-f]{6}$")
            for order, role in enumerate(_STYLE_PALETTE_DEFAULTS, start=1):
                raw = request.POST.get(f"palette_{role}", "").strip().upper()
                if not valid_hex.fullmatch(raw):
                    messages.error(request, f"Color inválido en {_STYLE_PALETTE_LABELS[role]}.")
                    return redirect("operations:development_project_styles", project_pk=project.pk)
                obj = palette.colors.filter(role=role).order_by("id").first()
                if obj:
                    obj.label = _STYLE_PALETTE_LABELS[role]
                    obj.hex_code = raw
                    obj.usage = _STYLE_PALETTE_USAGE[role]
                    obj.order = order
                    obj.save(update_fields=["label", "hex_code", "usage", "order", "updated_at"])
                    palette.colors.filter(role=role).exclude(pk=obj.pk).delete()
                else:
                    PaletteColor.objects.create(
                        palette=palette,
                        role=role,
                        label=_STYLE_PALETTE_LABELS[role],
                        hex_code=raw,
                        usage=_STYLE_PALETTE_USAGE[role],
                        order=order,
                    )
            palette.is_primary = True
            palette.save(update_fields=["is_primary", "updated_at"])
            ColorPalette.objects.filter(project=project, is_primary=True).exclude(pk=palette.pk).update(is_primary=False)
            log_activity(request.user, "development", "styles_palette_save", palette)
            messages.success(request, "Paleta guardada.")

        return redirect("operations:development_project_styles", project_pk=project.pk)

    typography = _normalized_typography_config(sheet)
    palette_map = {item.role: item.hex_code for item in palette.colors.all()}
    palette_rows = [
        {
            "role": role,
            "label": _STYLE_PALETTE_LABELS[role],
            "hex": palette_map.get(role, default),
            "usage": _STYLE_PALETTE_USAGE[role],
        }
        for role, default in _STYLE_PALETTE_DEFAULTS.items()
    ]

    return render(
        request,
        "operations/development_styles.html",
        {
            "project": project,
            "sheet": sheet,
            "can_manage_styles": can_manage_styles,
            "typography": typography,
            "palette": palette,
            "palette_rows": palette_rows,
            "default_header": _DEFAULT_HEADER_STRUCTURE,
        },
    )


@role_required("developer")
def web_production_sheet(
    request,
    project_pk,
):
    project = get_object_or_404(
        Project.objects.select_related(
            "client",
            "purchased_plan__plan",
        ),
        pk=project_pk,
    )

    if not can_access_project(
        request.user,
        project,
    ):
        raise PermissionDenied(
            "Este proyecto no está asignado a Desarrollo."
        )

    can_manage_project = (
        _can_manage_full_development_project(
            request.user,
            project,
        )
    )

    sheet, created = (
        WebProductionSheet.objects
        .get_or_create(
            project=project,
            defaults={
                "updated_by":
                    request.user,
                "main_page_target":
                    8,
            },
        )
    )

    if created:
        ensure_web_production_structure(
            sheet=sheet,
            main_page_target=8,
            county_target=0,
            services_per_county_target=0,
            cities_per_county_target=0,
            user=request.user,
        )

    (
        questionnaire,
        service_catalog,
        seo_strategy,
    ) = _technical_production_inputs(
        project
    )

    technical_payload = (
        website_answer_payload(questionnaire)
        if questionnaire
        else {}
    )

    technical_data_definitions = [
        ("company_description", "Descripción del negocio", "General"),
        ("business_logic", "Lógica del negocio", "General"),
        ("main_services", "Servicios principales", "Servicios"),
        ("service_areas", "Áreas de servicio", "Cobertura"),
        ("coverage", "Cobertura", "Cobertura"),
        ("future_expansion", "Expansión futura", "Cobertura"),
        ("contact_numbers", "Teléfonos", "Contacto"),
        ("business_hours", "Horarios", "Contacto"),
        ("is_24_7", "Disponibilidad 24/7", "Contacto"),
        ("quotes", "Cotizaciones / estimados", "Contacto"),
        ("slogan", "Slogan", "Marca"),
        ("has_mission_vision", "Misión y visión", "Marca"),
        ("certifications", "Certificaciones", "Empresa"),
        ("warranties", "Garantías", "Empresa"),
        ("experience_years", "Años de experiencia", "Empresa"),
        ("show_team", "Equipo / About", "Empresa"),
        ("has_social", "Redes sociales", "Marketing"),
        ("seo_page_strategy", "Estrategia SEO", "SEO"),
        ("website_structure", "Estructura web", "SEO"),
        ("resources", "Recursos", "Recursos"),
        ("website_forms", "Formularios del sitio", "Recursos"),
    ]

    technical_data_rows = []
    for key, label, group in technical_data_definitions:
        item = technical_payload.get(key) or {}
        text = str(item.get("text") or "").strip()
        raw_json = item.get("json") or {}

        if not text and isinstance(raw_json, dict):
            values = []
            for candidate_key in (
                "items", "areas", "numbers", "phones",
                "services", "values", "options",
            ):
                candidate = raw_json.get(candidate_key)
                if isinstance(candidate, list):
                    for entry in candidate:
                        if isinstance(entry, dict):
                            value = (
                                entry.get("name")
                                or entry.get("label")
                                or entry.get("value")
                                or entry.get("number")
                            )
                        else:
                            value = entry
                        if value:
                            values.append(str(value).strip())
                    if values:
                        break
            if values:
                text = " · ".join(values)

        technical_data_rows.append({
            "key": key,
            "label": label,
            "group": group,
            "text": text,
            "complete": bool(item.get("complete")),
            "updated_by": item.get("updated_by"),
            "updated_at": item.get("updated_at"),
        })

    technical_area_item = technical_payload.get("service_areas") or {}
    technical_area_candidates = []
    if technical_area_item.get("complete"):
        for area in (technical_area_item.get("json") or {}).get("items", []):
            if not isinstance(area, dict):
                continue
            area_type = str(area.get("type") or "").strip().lower()
            area_name = str(area.get("name") or "").strip()
            if area_type in {"state", "county", "city"} and area_name:
                technical_area_candidates.append({"type": area_type, "name": area_name})

    technical_sync_counts = {
        "counties": sum(1 for item in technical_area_candidates if item["type"] == "county"),
        "cities": sum(1 for item in technical_area_candidates if item["type"] == "city"),
        "states": sum(1 for item in technical_area_candidates if item["type"] == "state"),
        "services": len(service_catalog) if (technical_payload.get("main_services") or {}).get("complete") else 0,
    }

    structure_form = (
        WebProductionStructureForm(
            initial={
                "main_page_target":
                    sheet.main_page_target,

                "county_target":
                    sheet.county_target,

                "services_per_county_target":
                    sheet.services_per_county_target,

                "cities_per_county_target":
                    sheet.cities_per_county_target,
            }
        )
    )

    project_developers = list(
        UserAccount.objects.filter(
            Q(assigned_projects_v2__project=project)
            | Q(role=UserAccount.Role.DEVELOPER),
            is_active=True,
        )
        .distinct()
        .order_by("first_name", "last_name", "email")
    )

    users = {user.pk: user for user in project_developers}

    project_reviewers = project_developers
    reviewer_users = users

    if request.method == "POST":
        action = request.POST.get(
            "action",
            "",
        )

        if action == "mark_production_notification_read":
            notification_id = request.POST.get("notification_id", "").strip()
            if notification_id.isdigit():
                WebProductionNotification.objects.filter(
                    pk=int(notification_id),
                    sheet=sheet,
                    recipient=request.user,
                ).update(is_read=True)
            return redirect("operations:web_production_sheet", project_pk=project.pk)

        if action == "mark_all_production_notifications_read":
            WebProductionNotification.objects.filter(
                sheet=sheet,
                recipient=request.user,
                is_read=False,
            ).update(is_read=True)
            return redirect("operations:web_production_sheet", project_pk=project.pk)

        admin_only_actions = {
            "add_internal_section",
            "delete_internal_section",
            "save_button_style",
            "delete_button_style",
            "generate_structure",
            "sync_technical_structure",
            "add_page",
            "add_county",
            "add_service",
            "add_city",
            "apply_global_service",
            "delete_page",
            "delete_county",
            "delete_service",
            "delete_city",
            "save_general",
        }

        if action in admin_only_actions:
            _require_project_production_admin(
                can_manage_project
            )

        if action == "quick_update_row":
            row_type = request.POST.get("row_type", "").strip()
            row_id = request.POST.get("row_id", "").strip()
            field = request.POST.get("field", "").strip()
            value = request.POST.get("value", "").strip()
            wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"

            def quick_error(message):
                if wants_json:
                    return JsonResponse({"ok": False, "error": message}, status=400)
                messages.error(request, message)
                return redirect("operations:web_production_sheet", project_pk=project.pk)

            model_map = {
                "page": (WebProductionPage, {"sheet": sheet}),
                "county": (WebProductionCounty, {"sheet": sheet}),
                "service": (WebProductionCountyService, {"county__sheet": sheet}),
                "city": (WebProductionCity, {"sheet": sheet}),
                "internal_section": (WebProductionInternalSection, {"sheet": sheet}),
            }
            if row_type not in model_map or not row_id.isdigit():
                return quick_error("Edición rápida inválida.")

            model, scope = model_map[row_type]
            obj = model.objects.filter(pk=int(row_id), **scope).first()
            if obj is None:
                return quick_error("No se encontró el registro dentro de esta ficha de producción.")

            history_before = _production_history_snapshot(obj)

            if field == "responsible":
                if not can_manage_project:
                    raise PermissionDenied(
                        "Solo el responsable principal o Gerencia puede reasignar responsables."
                    )
                if value and (not value.isdigit() or int(value) not in users):
                    return quick_error("El responsable no pertenece al equipo disponible de Desarrollo.")
                obj.responsible = users.get(int(value)) if value.isdigit() else None
            elif field == "review_status":
                if not _can_review_production_row(
                    request.user,
                    obj,
                    can_manage_project=can_manage_project,
                ):
                    return quick_error(
                        "Solo el revisor asignado puede marcar la revisión de este elemento."
                    )
                if getattr(obj, "workflow_status", None) != ProductionWorkStatus.IN_REVIEW:
                    return quick_error(
                        "La revisión solo puede registrarse cuando el elemento está En revisión."
                    )
            else:
                _require_production_row_edit(
                    request.user,
                    obj,
                    can_manage_project=can_manage_project,
                )

            if field == "responsible":
                pass
            elif field == "complexity":
                if not can_manage_project:
                    raise PermissionDenied(
                        "Solo el responsable principal o Gerencia puede cambiar la complejidad."
                    )
                if value not in {"S", "M", "C"}:
                    return quick_error("Complejidad inválida.")
                obj.complexity = value
                obj.points = {"S": 1, "M": 2, "C": 3}[value]
            elif field == "name" and hasattr(obj, "name"):
                if not can_manage_project:
                    raise PermissionDenied(
                        "Solo el responsable principal o Gerencia puede cambiar nombres estructurales."
                    )
                if not value:
                    return quick_error("El nombre no puede quedar vacío.")
                obj.name = value
                if isinstance(obj, WebProductionCountyService) and hasattr(obj, "service_name"):
                    obj.service_name = value
            elif field == "slug" and hasattr(obj, "slug"):
                obj.slug = slugify(value)
            elif field == "keyword" and hasattr(obj, "keyword"):
                obj.keyword = value
                obj.slug = slugify(value)
            elif field == "created" and isinstance(obj, WebProductionInternalSection):
                if value not in {"yes", "no"}:
                    return quick_error("Valor de creada inválido.")
                obj.created = value == "yes"
            elif field == "workflow_status" and hasattr(obj, "workflow_status"):
                allowed = {
                    "not_started": ProductionWorkStatus.NOT_STARTED,
                    "in_progress": ProductionWorkStatus.IN_PROGRESS,
                    "in_review": ProductionWorkStatus.IN_REVIEW,
                    "complete": ProductionWorkStatus.COMPLETE,
                }
                if value not in allowed:
                    return quick_error("Estado inválido.")
                if (
                    value == "complete"
                    and not _can_force_complete_production_row(request.user)
                ):
                    return quick_error(
                        "Completo solo puede establecerse directamente por Gerencia Global o Superuser. El revisor debe usar Aprobar."
                    )
                if (
                    value == "in_review"
                    and not getattr(obj, "reviewer_id", None)
                ):
                    return quick_error(
                        "Selecciona un revisor antes de enviar este elemento a revisión."
                    )
                obj.workflow_status = allowed[value]
            elif field == "state":
                return quick_error(
                    "Lista es un campo interno y ya no se modifica por separado. Usa el Estado del flujo de producción."
                )
            elif field == "review_status" and hasattr(obj, "review_status"):
                if value not in {CompleteStatus.COMPLETE, CompleteStatus.INCOMPLETE}:
                    return quick_error("Valor de Revisión inválido.")

                review_note = request.POST.get("review_note", "").strip()

                if value == CompleteStatus.COMPLETE:
                    obj.review_status = CompleteStatus.COMPLETE
                    obj.workflow_status = ProductionWorkStatus.COMPLETE
                else:
                    if not review_note:
                        return quick_error(
                            "Escribe una observación antes de devolver el elemento a corrección."
                        )
                    obj.review_status = CompleteStatus.INCOMPLETE
                    obj.workflow_status = ProductionWorkStatus.IN_PROGRESS
            else:
                return quick_error("Campo de edición rápida inválido.")

            obj.updated_by = request.user
            _sync_legacy_production_flags(obj)
            obj.save()
            _record_production_changes(
                sheet, obj, row_type, request.user, history_before,
                review_note=request.POST.get("review_note", "").strip(),
            )
            sheet.updated_by = request.user
            sheet.save(update_fields=["updated_by", "updated_at"])

            if wants_json:
                return JsonResponse({
                    "ok": True,
                    "field": field,
                    "value": value,
                    "slug": getattr(obj, "slug", ""),
                    "points": getattr(obj, "points", None),
                    "workflow_status": getattr(obj, "workflow_status", ""),
                })

            messages.success(request, "Cambio guardado.")
            return redirect("operations:web_production_sheet", project_pk=project.pk)

        if action == "save_page":
            row_id = request.POST.get(
                "row_id",
                "",
            ).strip()

            page = get_object_or_404(
                WebProductionPage,
                pk=row_id,
                sheet=sheet,
            )

            _require_production_row_edit(
                request.user,
                page,
                can_manage_project=can_manage_project,
            )

            _update_seo_row(
                page,
                request,
                f"p_{page.pk}",
                users,
                reviewer_users,
                allow_assignment_changes=can_manage_project,
                allow_structure_changes=can_manage_project,
                allow_complete=_can_force_complete_production_row(request.user),
                allow_review_status=_can_review_production_row(
                    request.user,
                    page,
                    can_manage_project=can_manage_project,
                ),
                sheet=sheet,
                row_type="page",
            )

            sheet.updated_by = (
                request.user
            )

            sheet.save(
                update_fields=[
                    "updated_by",
                    "updated_at",
                ]
            )

            log_activity(
                request.user,
                "development",
                "production_page_save",
                page,
                description=page.name,
            )

            messages.success(
                request,
                f"{page.name} guardada correctamente.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "save_county":
            row_id = request.POST.get(
                "row_id",
                "",
            ).strip()

            county = get_object_or_404(
                WebProductionCounty,
                pk=row_id,
                sheet=sheet,
            )

            _require_production_row_edit(
                request.user,
                county,
                can_manage_project=can_manage_project,
            )

            _update_seo_row(
                county,
                request,
                f"c_{county.pk}",
                users,
                reviewer_users,
                allow_assignment_changes=can_manage_project,
                allow_structure_changes=can_manage_project,
                allow_complete=_can_force_complete_production_row(request.user),
                allow_review_status=_can_review_production_row(
                    request.user,
                    county,
                    can_manage_project=can_manage_project,
                ),
                sheet=sheet,
                row_type="county",
            )

            sheet.updated_by = (
                request.user
            )

            sheet.save(
                update_fields=[
                    "updated_by",
                    "updated_at",
                ]
            )

            log_activity(
                request.user,
                "development",
                "production_county_save",
                county,
                description=county.name,
            )

            messages.success(
                request,
                f"{county.name} guardado correctamente.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "save_service":
            row_id = request.POST.get(
                "row_id",
                "",
            ).strip()

            service = (
                get_object_or_404(
                    WebProductionCountyService,
                    pk=row_id,
                    county__sheet=sheet,
                )
            )

            _require_production_row_edit(
                request.user,
                service,
                can_manage_project=can_manage_project,
            )

            _update_seo_row(
                service,
                request,
                f"s_{service.pk}",
                users,
                reviewer_users,
                allow_assignment_changes=can_manage_project,
                allow_structure_changes=can_manage_project,
                allow_complete=_can_force_complete_production_row(request.user),
                allow_review_status=_can_review_production_row(
                    request.user,
                    service,
                    can_manage_project=can_manage_project,
                ),
                sheet=sheet,
                row_type="service",
            )

            sheet.updated_by = (
                request.user
            )

            sheet.save(
                update_fields=[
                    "updated_by",
                    "updated_at",
                ]
            )

            log_activity(
                request.user,
                "development",
                "production_service_save",
                service,
                description=service.name,
            )

            messages.success(
                request,
                f"{service.name} guardado correctamente.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "save_city":
            row_id = request.POST.get(
                "row_id",
                "",
            ).strip()

            city = get_object_or_404(
                WebProductionCity,
                pk=row_id,
                sheet=sheet,
            )

            _require_production_row_edit(
                request.user,
                city,
                can_manage_project=can_manage_project,
            )

            _update_seo_row(
                city,
                request,
                f"city_{city.pk}",
                users,
                reviewer_users,
                allow_assignment_changes=can_manage_project,
                allow_structure_changes=can_manage_project,
                allow_complete=_can_force_complete_production_row(request.user),
                allow_review_status=_can_review_production_row(
                    request.user,
                    city,
                    can_manage_project=can_manage_project,
                ),
                sheet=sheet,
                row_type="city",
            )

            sheet.updated_by = (
                request.user
            )

            sheet.save(
                update_fields=[
                    "updated_by",
                    "updated_at",
                ]
            )

            log_activity(
                request.user,
                "development",
                "production_city_save",
                city,
                description=city.name,
            )

            messages.success(
                request,
                f"{city.name} guardada correctamente.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif (
            action
            == "save_internal_section"
        ):
            row_id = request.POST.get(
                "row_id",
                "",
            ).strip()

            section = (
                get_object_or_404(
                    WebProductionInternalSection,
                    pk=row_id,
                    sheet=sheet,
                )
            )

            _require_production_row_edit(
                request.user,
                section,
                can_manage_project=can_manage_project,
            )

            _update_internal_section(
                section,
                request,
                f"internal_{section.pk}",
                users,
                reviewer_users,
                allow_assignment_changes=can_manage_project,
                allow_structure_changes=can_manage_project,
                allow_complete=_can_force_complete_production_row(request.user),
                sheet=sheet,
                row_type="internal_section",
            )

            sheet.updated_by = (
                request.user
            )

            sheet.save(
                update_fields=[
                    "updated_by",
                    "updated_at",
                ]
            )

            log_activity(
                request.user,
                "development",
                "production_internal_section_save",
                section,
                description=section.name,
            )

            messages.success(
                request,
                f"{section.name} guardada correctamente.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "add_internal_section":
            order = (sheet.internal_sections.order_by("-order").values_list("order", flat=True).first() or 0) + 1
            section = WebProductionInternalSection.objects.create(
                sheet=sheet,
                name=(request.POST.get("section_name", "").strip() or f"Sección interna {order}"),
                complexity="S",
                points=1,
                order=order,
                updated_by=request.user,
            )
            log_activity(request.user, "development", "production_internal_section_add", section, description=section.name)
            messages.success(request, "Sección interna agregada.")
            return redirect("operations:web_production_sheet", project_pk=project.pk)

        elif action == "delete_internal_section":
            section = get_object_or_404(
                WebProductionInternalSection,
                pk=request.POST.get("row_id"),
                sheet=sheet,
            )
            label = section.name
            section.delete()
            log_activity(request.user, "development", "production_internal_section_delete", sheet, description=label)
            messages.success(request, "Sección interna eliminada.")
            return redirect("operations:web_production_sheet", project_pk=project.pk)

        elif action == "sync_technical_structure":
            if not questionnaire:
                messages.error(request, "No existe una Ficha Técnica Web conectada a este proyecto.")
                return redirect("operations:web_production_sheet", project_pk=project.pk)

            created_counties = 0
            created_cities = 0
            created_services = 0
            referenced_states = 0

            county_order = (sheet.counties.order_by("-order").values_list("order", flat=True).first() or 0)
            city_order = (sheet.cities.order_by("-order").values_list("order", flat=True).first() or 0)

            for area in technical_area_candidates:
                area_type = area["type"]
                area_name = area["name"]
                if area_type == "state":
                    referenced_states += 1
                    continue
                if area_type == "county":
                    if sheet.counties.filter(name__iexact=area_name).first() is None:
                        county_order += 1
                        WebProductionCounty.objects.create(
                            sheet=sheet, name=area_name, order=county_order, updated_by=request.user
                        )
                        created_counties += 1
                    continue
                if area_type == "city":
                    if sheet.cities.filter(name__iexact=area_name).first() is None:
                        city_order += 1
                        WebProductionCity.objects.create(
                            sheet=sheet, name=area_name, county=None, order=city_order, updated_by=request.user
                        )
                        created_cities += 1

            services_are_confirmed = bool((technical_payload.get("main_services") or {}).get("complete"))
            if seo_strategy == "client_services" and services_are_confirmed:
                for county in sheet.counties.all():
                    service_order = (county.services.order_by("-order").values_list("order", flat=True).first() or 0)
                    for service in service_catalog:
                        service_name = str(service.get("name") or "").strip()
                        if not service_name:
                            continue
                        if county.services.filter(service_name__iexact=service_name).first() is not None:
                            continue
                        service_order += 1
                        WebProductionCountyService.objects.create(
                            county=county,
                            service_name=service_name,
                            name=f"{service_name} {county.name}".strip(),
                            is_global=True,
                            order=service_order,
                            updated_by=request.user,
                        )
                        created_services += 1

            sheet.updated_by = request.user
            sheet.save(update_fields=["updated_by", "updated_at"])

            parts = [
                f"{created_counties} counties nuevos",
                f"{created_cities} ciudades nuevas",
                f"{created_services} servicios nuevos",
            ]
            if referenced_states:
                parts.append(f"{referenced_states} estados conservados solo como referencia")
            if seo_strategy != "client_services" and service_catalog:
                parts.append("los servicios no se generaron porque la estrategia requiere estudio SEO")

            messages.success(
                request,
                "Ficha Técnica sincronizada: " + "; ".join(parts) + ". No se borró ni sobrescribió estructura existente.",
            )
            return redirect("operations:web_production_sheet", project_pk=project.pk)

        elif action == "generate_structure":
            structure_form = (
                WebProductionStructureForm(
                    request.POST
                )
            )

            if structure_form.is_valid():
                ensure_web_production_structure(
                    sheet=sheet,
                    user=request.user,
                    **structure_form.cleaned_data,
                )

                messages.success(
                    request,
                    (
                        "Estructura completada "
                        "sin borrar información existente."
                    ),
                )

                return redirect(
                    "operations:web_production_sheet",
                    project_pk=project.pk,
                )

        elif action == "add_page":
            order = (
                sheet.pages
                .order_by(
                    "-order"
                )
                .values_list(
                    "order",
                    flat=True,
                )
                .first()
                or 0
            ) + 1

            obj = WebProductionPage(
                sheet=sheet,
                page_type=(
                    WebProductionPage
                    .PageType.EXTRA
                ),
                name=(
                    f"Página extra {order}"
                ),
                order=order,
                updated_by=request.user,
            )

            apply_seo_automation(
                obj
            )

            obj.save()

            log_activity(
                request.user,
                "development",
                "production_page_add",
                sheet,
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "add_county":
            order = (
                sheet.counties
                .order_by(
                    "-order"
                )
                .values_list(
                    "order",
                    flat=True,
                )
                .first()
                or 0
            ) + 1

            county = (
                WebProductionCounty(
                    sheet=sheet,
                    name=(
                        f"Condado {order}"
                    ),
                    order=order,
                    updated_by=(
                        request.user
                    ),
                )
            )

            apply_seo_automation(
                county
            )

            county.save()

            for index in range(
                sheet.services_per_county_target
            ):
                service = (
                    WebProductionCountyService(
                        county=county,
                        name=(
                            f"Servicio "
                            f"{index + 1} · "
                            f"{county.name}"
                        ),
                        order=index + 1,
                        updated_by=(
                            request.user
                        ),
                    )
                )

                apply_seo_automation(
                    service
                )

                service.save()

            for index in range(
                sheet.cities_per_county_target
            ):
                city = (
                    WebProductionCity(
                        sheet=sheet,
                        county=county,
                        name=(
                            f"Ciudad "
                            f"{index + 1}"
                        ),
                        order=index + 1,
                        updated_by=(
                            request.user
                        ),
                    )
                )

                apply_seo_automation(
                    city
                )

                city.save()

            log_activity(
                request.user,
                "development",
                "production_county_add",
                sheet,
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "add_service":
            county = (
                get_object_or_404(
                    WebProductionCounty,
                    pk=request.POST.get(
                        "county_id"
                    ),
                    sheet=sheet,
                )
            )

            order = (
                county.services
                .order_by(
                    "-order"
                )
                .values_list(
                    "order",
                    flat=True,
                )
                .first()
                or 0
            ) + 1

            service = (
                WebProductionCountyService(
                    county=county,
                    name=(
                        f"Servicio {order} · "
                        f"{county.name}"
                    ),
                    order=order,
                    updated_by=(
                        request.user
                    ),
                )
            )

            apply_seo_automation(
                service
            )

            service.save()

            log_activity(
                request.user,
                "development",
                "production_service_add",
                sheet,
                description=county.name,
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "add_city":
            order = (
                sheet.cities
                .order_by(
                    "-order"
                )
                .values_list(
                    "order",
                    flat=True,
                )
                .first()
                or 0
            ) + 1

            county_id = (
                request.POST.get(
                    "county_id",
                    "",
                ).strip()
            )

            county = (
                WebProductionCounty.objects
                .filter(
                    pk=county_id,
                    sheet=sheet,
                )
                .first()
                if county_id.isdigit()
                else None
            )

            if county:
                order = (
                    county.cities
                    .order_by(
                        "-order"
                    )
                    .values_list(
                        "order",
                        flat=True,
                    )
                    .first()
                    or 0
                ) + 1

            city = WebProductionCity(
                sheet=sheet,
                county=county,
                name=(
                    f"Ciudad {order}"
                ),
                order=order,
                updated_by=request.user,
            )

            apply_seo_automation(
                city
            )

            city.save()

            log_activity(
                request.user,
                "development",
                "production_city_add",
                sheet,
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "apply_global_service":
            selected = (
                request.POST.get(
                    "global_service_name",
                    "",
                ).strip()
            )

            if not selected:
                messages.warning(
                    request,
                    (
                        "Selecciona un servicio "
                        "para aplicarlo globalmente."
                    ),
                )

            else:
                created_count = 0

                for county in (
                    sheet.counties.all()
                ):
                    exists = (
                        county.services
                        .filter(
                            service_name__iexact=selected
                        )
                        .exists()
                    )

                    if exists:
                        continue

                    order = (
                        county.services
                        .order_by(
                            "-order"
                        )
                        .values_list(
                            "order",
                            flat=True,
                        )
                        .first()
                        or 0
                    ) + 1

                    obj = (
                        WebProductionCountyService(
                            county=county,
                            service_name=selected,
                            name=(
                                f"{selected} "
                                f"{county.name}"
                            ).strip(),
                            is_global=True,
                            order=order,
                            updated_by=(
                                request.user
                            ),
                        )
                    )

                    apply_seo_automation(
                        obj
                    )

                    obj.save()

                    created_count += 1

                log_activity(
                    request.user,
                    "development",
                    "production_global_service",
                    sheet,
                    description=selected,
                )

                messages.success(
                    request,
                    (
                        f"{selected}: creado en "
                        f"{created_count} condados "
                        "que no lo tenían."
                    ),
                )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action in {
            "delete_page",
            "delete_county",
            "delete_service",
            "delete_city",
        }:
            row_id = (
                request.POST.get(
                    "row_id"
                )
            )

            if action == "delete_page":
                obj = get_object_or_404(
                    WebProductionPage,
                    pk=row_id,
                    sheet=sheet,
                )

            elif action == "delete_county":
                obj = get_object_or_404(
                    WebProductionCounty,
                    pk=row_id,
                    sheet=sheet,
                )

            elif action == "delete_service":
                obj = get_object_or_404(
                    WebProductionCountyService,
                    pk=row_id,
                    county__sheet=sheet,
                )

            else:
                obj = get_object_or_404(
                    WebProductionCity,
                    pk=row_id,
                    sheet=sheet,
                )

            label = obj.name
            obj.delete()

            log_activity(
                request.user,
                "development",
                action,
                sheet,
                description=label,
            )

            messages.success(
                request,
                "Elemento eliminado.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        elif action == "save_general":
            sheet.notes = (
                request.POST.get(
                    "sheet_notes",
                    "",
                ).strip()
            )

            sheet.updated_by = (
                request.user
            )

            sheet.save(
                update_fields=[
                    "notes",
                    "updated_by",
                    "updated_at",
                ]
            )

            log_activity(
                request.user,
                "development",
                "production_general_save",
                sheet,
            )

            messages.success(
                request,
                "Configuración general guardada.",
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

    pages = list(
        sheet.pages.select_related(
            "responsible",
            "reviewer",
            "updated_by",
        )
    )

    counties = list(
        sheet.counties
        .select_related(
            "responsible",
            "reviewer",
            "updated_by",
        )
        .prefetch_related(
            "services__responsible",
            "services__reviewer",
            "services__updated_by",
            "cities__responsible",
            "cities__reviewer",
            "cities__updated_by",
        )
    )

    cities = list(
        sheet.cities.select_related(
            "county",
            "responsible",
            "reviewer",
            "updated_by",
        )
    )

    internal_sections = list(
        sheet.internal_sections
        .select_related(
            "responsible",
            "reviewer",
            "updated_by",
        )
    )

    unassigned_cities = [
        city
        for city in cities
        if not city.county_id
    ]

    developers = project_developers

    all_rows = (
        pages
        + counties
        + [
            service
            for county in counties
            for service
            in county.services.all()
        ]
        + cities
    )

    production_rows = (
        all_rows
        + internal_sections
    )

    editable_row_keys = []
    reviewable_row_keys = []

    row_groups = (
        ("page", pages),
        ("county", counties),
        (
            "service",
            [
                service
                for county in counties
                for service in county.services.all()
            ],
        ),
        ("city", cities),
        ("internal_section", internal_sections),
    )

    history_map = defaultdict(list)
    for history in (
        WebProductionHistory.objects
        .filter(sheet=sheet)
        .select_related("actor")
        .order_by("-created_at", "-id")[:1500]
    ):
        history_map[(history.row_type, history.row_id)].append(history)

    history_event_labels = {
        "content_updated": "Contenido actualizado",
        "status_changed": "Estado actualizado",
        "sent_to_review": "Enviado a revisión",
        "review_returned": "Requiere cambios",
        "review_approved": "Aprobada",
        "responsible_changed": "Responsable actualizado",
        "reviewer_changed": "Revisor actualizado",
    }
    history_status_labels = {
        ProductionWorkStatus.NOT_STARTED: "Sin iniciar",
        ProductionWorkStatus.IN_PROGRESS: "En progreso",
        ProductionWorkStatus.IN_REVIEW: "En revisión",
        ProductionWorkStatus.COMPLETE: "Completo",
        "": "",
    }

    for row_type, rows in row_groups:
        for row in rows:
            row.history_items = history_map.get((row_type, row.pk), [])[:20]
            for history in row.history_items:
                history.event_label = history_event_labels.get(history.event, history.event.replace("_", " ").title())
                history.from_status_label = history_status_labels.get(history.from_status, history.from_status)
                history.to_status_label = history_status_labels.get(history.to_status, history.to_status)
            row.can_edit = _can_edit_production_row(
                request.user,
                row,
                can_manage_project=can_manage_project,
            )
            row.can_review = (
                _can_review_production_row(
                    request.user,
                    row,
                    can_manage_project=can_manage_project,
                )
                and getattr(row, "workflow_status", None) == ProductionWorkStatus.IN_REVIEW
            )
            if row.can_edit:
                editable_row_keys.append(
                    f"{row_type}:{row.pk}"
                )
            workflow_value = getattr(row, "workflow_status", None)
            review_value = getattr(row, "review_status", None)
            latest_review_event = next(
                (
                    history.event
                    for history in row.history_items
                    if history.event
                    in {
                        "review_returned",
                        "sent_to_review",
                        "review_approved",
                    }
                ),
                "",
            )

            if workflow_value == ProductionWorkStatus.COMPLETE:
                row.review_label = "Aprobada"
                row.review_tone = "approved"
            elif workflow_value == ProductionWorkStatus.IN_REVIEW:
                row.review_label = "Pendiente de revisión"
                row.review_tone = "pending"
            elif latest_review_event == "review_returned":
                row.review_label = "Requiere cambios"
                row.review_tone = "changes"
            else:
                row.review_label = "Sin revisión"
                row.review_tone = "none"

            if row.can_review:
                reviewable_row_keys.append(
                    f"{row_type}:{row.pk}"
                )

    project_assignment_user_ids = set(
        project.assignments.filter(
            area="development",
            status__in=["assigned", "active"],
        ).values_list(
            "user_id",
            flat=True,
        )
    )

    responsible_user_ids = {
        row.responsible_id
        for row in production_rows
        if row.responsible_id
    }

    summary_user_ids = (
        project_assignment_user_ids
        | responsible_user_ids
    )

    developer_summary = {
        developer.pk: {
            "id": developer.pk,
            "name": developer.display_name,
            "assigned": 0,
            "in_progress": 0,
            "in_review": 0,
            "changes": 0,
            "approved": 0,
        }
        for developer in project_developers
        if developer.pk in summary_user_ids
    }

    for row in production_rows:
        responsible_id = getattr(
            row,
            "responsible_id",
            None,
        )

        if responsible_id not in developer_summary:
            continue

        summary = developer_summary[responsible_id]
        summary["assigned"] += 1

        if row.review_label == "Aprobada":
            summary["approved"] += 1
        elif row.review_label == "Requiere cambios":
            summary["changes"] += 1
        elif row.workflow_status == ProductionWorkStatus.IN_REVIEW:
            summary["in_review"] += 1
        elif row.workflow_status == ProductionWorkStatus.IN_PROGRESS:
            summary["in_progress"] += 1

    developer_summary_rows = sorted(
        developer_summary.values(),
        key=lambda item: item["name"].lower(),
    )

    total_project_items = len(production_rows)
    project_not_started = sum(
        1
        for row in production_rows
        if (
            row.workflow_status == ProductionWorkStatus.NOT_STARTED
            and row.review_label != "Requiere cambios"
        )
    )
    project_in_progress = sum(
        1
        for row in production_rows
        if (
            row.workflow_status == ProductionWorkStatus.IN_PROGRESS
            and row.review_label != "Requiere cambios"
        )
    )
    project_in_review = sum(
        1
        for row in production_rows
        if row.workflow_status == ProductionWorkStatus.IN_REVIEW
    )
    project_changes = sum(
        1
        for row in production_rows
        if row.review_label == "Requiere cambios"
    )
    project_approved = sum(
        1
        for row in production_rows
        if row.review_label == "Aprobada"
    )
    project_unassigned = sum(
        1
        for row in production_rows
        if not getattr(row, "responsible_id", None)
    )
    project_progress_percent = (
        round((project_approved / total_project_items) * 100)
        if total_project_items
        else 0
    )

    # Mantener puntos siempre sincronizados con la complejidad, incluso
    # para registros creados antes de la regla S=1, M=2, C=3.
    complexity_points = {"S": 1, "M": 2, "C": 3}
    for row in production_rows:
        expected_points = complexity_points.get(row.complexity)
        if expected_points is not None and row.points != expected_points:
            type(row).objects.filter(pk=row.pk).update(points=expected_points)
            row.points = expected_points

    total_rows = len(
        all_rows
    )

    completed_rows = sum(
        1
        for row in all_rows
        if (
            row.state
            == CompleteStatus.COMPLETE
        )
    )

    reviewed_rows = sum(
        1
        for row in all_rows
        if (
            row.review_status
            == CompleteStatus.COMPLETE
        )
    )

    completed_percent = (
        round(
            (
                completed_rows
                / total_rows
            )
            * 100
        )
        if total_rows
        else 0
    )

    reviewed_percent = (
        round(
            (
                reviewed_rows
                / total_rows
            )
            * 100
        )
        if total_rows
        else 0
    )

    total_production_items = len(
        production_rows
    )

    completed_items = sum(
        1
        for row in production_rows
        if (
            row.workflow_status
            == ProductionWorkStatus.COMPLETE
        )
    )

    review_items = sum(
        1
        for row in production_rows
        if (
            row.workflow_status
            == ProductionWorkStatus.IN_REVIEW
        )
    )

    progress_items = sum(
        1
        for row in production_rows
        if (
            row.workflow_status
            == ProductionWorkStatus.IN_PROGRESS
        )
    )

    pending_items = sum(
        1
        for row in production_rows
        if (
            row.workflow_status
            == ProductionWorkStatus.NOT_STARTED
        )
    )

    production_percent = (
        round(
            (
                completed_items
                / total_production_items
            )
            * 100
        )
        if total_production_items
        else 0
    )

    balance = {
        developer.pk: {
            "id": developer.pk,
            "name": developer.display_name,
            "production_points": 0,
            "internal_points": 0,
            "total_points": 0,
        }
        for developer in project_developers
        if developer.pk in summary_user_ids
    }

    unassigned_production_points = 0
    unassigned_internal_points = 0

    for row in all_rows:
        points = row.points or 0
        if row.responsible_id in balance:
            balance[row.responsible_id]["production_points"] += points
        else:
            unassigned_production_points += points

    for row in internal_sections:
        points = row.points or 0
        if row.responsible_id in balance:
            balance[row.responsible_id]["internal_points"] += points
        else:
            unassigned_internal_points += points

    for item in balance.values():
        item["total_points"] = (
            item["production_points"]
            + item["internal_points"]
        )

    balance_rows = list(balance.values())
    unassigned_points = (
        unassigned_production_points
        + unassigned_internal_points
    )
    unassigned_items = 0

    strategy_label = {
        "study":
            (
                "Estudio SEO: elegir servicios "
                "por tendencia/oportunidad"
            ),

        "client_services":
            (
                "Servicios del cliente: "
                "pueden aplicarse globalmente "
                "a todos los condados"
            ),
    }.get(
        seo_strategy,
        (
            "Sin estrategia definida "
            "en la ficha técnica"
        ),
    )

    production_notifications = list(
        WebProductionNotification.objects
        .filter(sheet=sheet, recipient=request.user)
        .select_related("actor")
        .order_by("-created_at", "-id")[:20]
    )
    production_notification_unread_count = (
        WebProductionNotification.objects
        .filter(
            sheet=sheet,
            recipient=request.user,
            is_read=False,
        )
        .count()
    )
    production_notification_labels = {
        "sent_to_review": "Enviado a revisión",
        "review_returned": "Requiere cambios",
        "review_approved": "Aprobado",
    }
    for item in production_notifications:
        item.event_label = production_notification_labels.get(
            item.event, item.event.replace("_", " ").title()
        )

    return render(
        request,
        "operations/development_production.html",
        {
            "project": project,
            "sheet": sheet,
            "production_notifications": production_notifications,
            "production_notification_unread_count": production_notification_unread_count,
            "structure_form":
                structure_form,

            "pages": pages,
            "counties": counties,
            "cities": cities,

            "internal_sections":
                internal_sections,

            "unassigned_cities":
                unassigned_cities,

            "developers":
                developers,

            "developer_summary_rows":
                developer_summary_rows,

            "total_project_items":
                total_project_items,

            "project_not_started":
                project_not_started,

            "project_in_progress":
                project_in_progress,

            "project_in_review":
                project_in_review,

            "project_changes":
                project_changes,

            "project_approved":
                project_approved,

            "project_unassigned":
                project_unassigned,

            "project_progress_percent":
                project_progress_percent,

            "reviewers":
                project_reviewers,

            "can_manage_project":
                can_manage_project,

            "can_force_complete":
                _can_force_complete_production_row(request.user),

            "editable_row_keys":
                editable_row_keys,

            "reviewable_row_keys":
                reviewable_row_keys,

            "service_catalog":
                service_catalog,

            "technical_data_rows":
                technical_data_rows,

            "technical_sync_counts":
                technical_sync_counts,

            "technical_questionnaire":
                questionnaire,

            "seo_strategy":
                seo_strategy,

            "strategy_label":
                strategy_label,

            "total_rows":
                total_rows,

            "completed_rows":
                completed_rows,

            "reviewed_rows":
                reviewed_rows,

            "completed_percent":
                completed_percent,

            "reviewed_percent":
                reviewed_percent,

            "production_statuses":
                ProductionWorkStatus.choices,

            "total_production_items":
                total_production_items,

            "completed_items":
                completed_items,

            "review_items":
                review_items,

            "progress_items":
                progress_items,

            "pending_items":
                pending_items,

            "production_percent":
                production_percent,

            "balance_rows":
                balance_rows,

            "unassigned_points":
                unassigned_points,

            "unassigned_production_points":
                unassigned_production_points,

            "unassigned_internal_points":
                unassigned_internal_points,

            "unassigned_items":
                unassigned_items,

            "questionnaire":
                questionnaire,
        },
    )


def _production_row_for(
    sheet,
    row_type,
    row_id,
):
    mapping = {
        "page": (
            WebProductionPage,
            {
                "sheet":
                    sheet
            },
        ),

        "county": (
            WebProductionCounty,
            {
                "sheet":
                    sheet
            },
        ),

        "service": (
            WebProductionCountyService,
            {
                "county__sheet":
                    sheet
            },
        ),

        "city": (
            WebProductionCity,
            {
                "sheet":
                    sheet
            },
        ),

        "internal_section": (
            WebProductionInternalSection,
            {
                "sheet":
                    sheet
            },
        ),
    }

    model_info = mapping.get(
        row_type
    )

    if not model_info:
        return None

    model, scope = (
        model_info
    )

    return model.objects.filter(
        pk=row_id,
        **scope,
    ).first()


@role_required("developer")
@require_POST
def web_production_quick_toggle(
    request,
    project_pk,
):
    project = get_object_or_404(
        Project,
        pk=project_pk,
    )

    if not can_access_project(
        request.user,
        project,
    ):
        raise PermissionDenied(
            "Este proyecto no está asignado a Desarrollo."
        )

    sheet = get_object_or_404(
        WebProductionSheet,
        project=project,
    )

    row_type = request.POST.get(
        "row_type",
        "",
    )

    row_id = request.POST.get(
        "row_id",
        "",
    )

    field = request.POST.get(
        "field",
        "",
    )

    value = request.POST.get(
        "value",
        "",
    )

    if not str(
        row_id
    ).isdigit():
        messages.error(
            request,
            "Cambio rápido inválido.",
        )

        return redirect(
            "operations:web_production_sheet",
            project_pk=project.pk,
        )

    obj = _production_row_for(
        sheet,
        row_type,
        int(
            row_id
        ),
    )

    if not obj:
        messages.error(
            request,
            (
                "No se encontró la fila "
                "de producción."
            ),
        )

        return redirect(
            "operations:web_production_sheet",
            project_pk=project.pk,
        )

    can_manage_project = _can_manage_full_development_project(
        request.user,
        project,
    )
    history_before = _production_history_snapshot(obj)

    if field == "review_status":
        if not _can_review_production_row(
            request.user,
            obj,
            can_manage_project=can_manage_project,
        ):
            raise PermissionDenied(
                "Solo el revisor asignado puede revisar este elemento."
            )
        if getattr(obj, "workflow_status", None) != ProductionWorkStatus.IN_REVIEW:
            messages.error(
                request,
                "La revisión solo puede registrarse cuando el elemento está En revisión.",
            )
            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )
    else:
        _require_production_row_edit(
            request.user,
            obj,
            can_manage_project=can_manage_project,
        )

    if field == "workflow_status":
        if not hasattr(
            obj,
            "workflow_status",
        ):
            messages.error(
                request,
                (
                    "Este elemento no admite "
                    "estado de producción."
                ),
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        if (
            value
            not in ProductionWorkStatus.values
        ):
            messages.error(
                request,
                (
                    "Estado de producción "
                    "inválido."
                ),
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        if (
            value == ProductionWorkStatus.COMPLETE
            and not _can_force_complete_production_row(request.user)
        ):
            messages.error(
                request,
                "Completo solo puede establecerse directamente por Gerencia Global o Superuser. El revisor debe usar Aprobar.",
            )
            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        if (
            value == ProductionWorkStatus.IN_REVIEW
            and not getattr(obj, "reviewer_id", None)
        ):
            messages.error(
                request,
                "Selecciona un revisor antes de enviar este elemento a revisión.",
            )
            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        obj.workflow_status = value

    elif field == "state":
        messages.error(
            request,
            "Lista es un campo interno y ya no se modifica por separado. Usa el Estado del flujo de producción.",
        )
        return redirect(
            "operations:web_production_sheet",
            project_pk=project.pk,
        )

    elif field == "review_status":
        if not hasattr(
            obj,
            "review_status",
        ):
            messages.error(
                request,
                (
                    "Este elemento no admite "
                    "revisión."
                ),
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        if (
            value
            not in CompleteStatus.values
        ):
            messages.error(
                request,
                (
                    "Estado de revisión "
                    "inválido."
                ),
            )

            return redirect(
                "operations:web_production_sheet",
                project_pk=project.pk,
            )

        review_note = request.POST.get(
            "review_note",
            "",
        ).strip()

        if value == CompleteStatus.COMPLETE:
            obj.review_status = CompleteStatus.COMPLETE
            obj.workflow_status = ProductionWorkStatus.COMPLETE
        else:
            if not review_note:
                messages.error(
                    request,
                    "Escribe una observación antes de devolver el elemento a corrección.",
                )
                return redirect(
                    "operations:web_production_sheet",
                    project_pk=project.pk,
                )

            obj.review_status = CompleteStatus.INCOMPLETE
            obj.workflow_status = ProductionWorkStatus.IN_PROGRESS


    else:
        messages.error(
            request,
            "Cambio rápido inválido.",
        )

        return redirect(
            "operations:web_production_sheet",
            project_pk=project.pk,
        )

    obj.updated_by = (
        request.user
    )
    _sync_legacy_production_flags(obj)

    obj.save()

    _record_production_changes(
        sheet, obj, row_type, request.user, history_before,
        review_note=request.POST.get("review_note", "").strip(),
    )

    sheet.updated_by = (
        request.user
    )

    sheet.save(
        update_fields=[
            "updated_by",
            "updated_at",
        ]
    )

    log_activity(
        request.user,
        "development",
        "production_quick_toggle",
        obj,
        description=(
            f"{field}: {value}"
        ),
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "field": field,
            "value": value,
        })

    return redirect(
        "operations:web_production_sheet",
        project_pk=project.pk,
    )

@role_required("developer")
def development_tasks(request):
    from django.utils import timezone
    from .models import DevelopmentTask

    can_assign = bool(
        request.user.is_superuser
        or getattr(request.user, "role", "") == "manager"
    )

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "mark_task_notification_read":
            notification = get_object_or_404(
                DevelopmentTaskNotification,
                pk=request.POST.get("notification_id"),
                recipient=request.user,
            )
            if not notification.is_read:
                notification.is_read = True
                notification.save(update_fields=["is_read"])
            return redirect("operations:development_tasks")

        if action == "mark_all_task_notifications_read":
            DevelopmentTaskNotification.objects.filter(
                recipient=request.user,
                is_read=False,
            ).update(is_read=True)
            return redirect("operations:development_tasks")

        if action == "create":
            if not can_assign:
                raise PermissionDenied("No tienes permiso para asignar tareas.")

            title = (request.POST.get("title") or "").strip()
            assigned_to_id = (request.POST.get("assigned_to") or "").strip()
            assigned_date = (request.POST.get("assigned_date") or "").strip()

            if not title or not assigned_to_id or not assigned_date:
                payload = {"ok": False, "message": "Completa tarea, desarrollador y fecha de asignación."}
                return JsonResponse(payload, status=400) if request.headers.get("x-requested-with") == "XMLHttpRequest" else redirect("operations:development_tasks")

            assigned_to = get_object_or_404(
                UserAccount,
                pk=assigned_to_id,
                role="developer",
                is_active=True,
            )

            project = None
            project_id = (request.POST.get("project_id") or "").strip()
            if project_id:
                project = get_object_or_404(Project, pk=project_id)

            due_date = (request.POST.get("due_date") or "").strip() or None
            priority = (request.POST.get("priority") or "medium").strip()
            if priority not in {"low", "medium", "high"}:
                priority = "medium"

            task = DevelopmentTask.objects.create(
                title=title,
                description=(request.POST.get("description") or "").strip(),
                project=project,
                assigned_to=assigned_to,
                assigned_by=request.user,
                assigned_date=assigned_date,
                due_date=due_date,
                priority=priority,
                status="pending",
                assignment_note=(request.POST.get("assignment_note") or "").strip(),
                updated_by=request.user,
            )

            # Recargar desde PostgreSQL para convertir DateField
            # de string a datetime.date antes de usar strftime().
            task.refresh_from_db()

            log_activity(
                request.user,
                "operations",
                "development_task_create",
                task,
            )

            if assigned_to.pk != request.user.pk:
                project_label = (
                    f"Proyecto: {project.project_code} · {project.name}. "
                    if project
                    else "Actividad general. "
                )
                due_label = (
                    f"Fecha objetivo: {task.due_date.strftime('%d/%m/%Y')}. "
                    if task.due_date
                    else ""
                )
                DevelopmentTaskNotification.objects.create(
                    task=task,
                    recipient=assigned_to,
                    actor=request.user,
                    event="task_assigned",
                    message=(
                        f"Te asignaron la tarea ‘{task.title}’. "
                        f"{project_label}{due_label}"
                        f"Prioridad: {task.get_priority_display()}."
                    ),
                )

                # Correo al desarrollador asignado. La tarea nunca falla si el SMTP
                # no está configurado o el proveedor de correo no responde.
                recipient_email = (assigned_to.email or "").strip()
                if recipient_email:
                    task_url = request.build_absolute_uri(
                        reverse("operations:development_tasks")
                    )
                    actor_name = (
                        request.user.get_full_name().strip()
                        or request.user.email
                        or "Gerencia"
                    )
                    project_name = (
                        f"{project.project_code} · {project.name}"
                        if project
                        else "Actividad general"
                    )
                    due_text = (
                        task.due_date.strftime("%d/%m/%Y")
                        if task.due_date
                        else "Sin fecha objetivo"
                    )
                    email_body = "\n".join([
                        f"Hola {assigned_to.get_full_name().strip() or assigned_to.email},",
                        "",
                        "Se te ha asignado una nueva tarea en el CRM de CEO Marketing.",
                        "",
                        f"Tarea: {task.title}",
                        f"Proyecto: {project_name}",
                        f"Prioridad: {task.get_priority_display()}",
                        f"Fecha de asignación: {task.assigned_date.strftime('%d/%m/%Y')}",
                        f"Fecha objetivo: {due_text}",
                        f"Asignado por: {actor_name}",
                        f"Descripción: {task.description or 'Sin descripción adicional'}",
                        f"Nota de asignación: {task.assignment_note or 'Sin nota adicional'}",
                        "",
                        "Puedes revisar la tarea aquí:",
                        task_url,
                        "",
                        "CRM CEO Interno",
                    ])
                    send_development_task_email.delay(
                        f"Nueva tarea asignada: {task.title}",
                        email_body,
                        recipient_email,
                    )

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({
                    "ok": True,
                    "task_id": task.pk,
                    "message": "Tarea asignada correctamente.",
                })
            messages.success(request, "Tarea asignada.")
            return redirect("operations:development_tasks")

        if action == "update":
            task = get_object_or_404(DevelopmentTask, pk=request.POST.get("task_id"))
            if not can_assign and task.assigned_to_id != request.user.id:
                raise PermissionDenied("No puedes modificar esta tarea.")

            status = (request.POST.get("status") or task.status).strip()
            valid_statuses = {"pending", "in_progress", "issue", "completed"}
            if status not in valid_statuses:
                status = task.status

            issue_reason = (request.POST.get("issue_reason") or "").strip()
            if status == "issue" and not issue_reason:
                payload = {"ok": False, "message": "Debes registrar el motivo del inconveniente."}
                return JsonResponse(payload, status=400) if request.headers.get("x-requested-with") == "XMLHttpRequest" else redirect("operations:development_tasks")

            task.status = status
            task.issue_reason = issue_reason if status == "issue" else ""
            if "developer_note" in request.POST:
                task.developer_note = (request.POST.get("developer_note") or "").strip()
            task.completed_at = timezone.now() if status == "completed" else None
            task.updated_by = request.user
            task.save(update_fields=["status", "issue_reason", "developer_note", "completed_at", "updated_by", "updated_at"])
            log_activity(request.user, "operations", "development_task_update", task)

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"ok": True, "status": task.status})
            messages.success(request, "Tarea actualizada.")
            return redirect("operations:development_tasks")

    qs = DevelopmentTask.objects.select_related("project", "assigned_to", "assigned_by").all()
    if not can_assign:
        qs = qs.filter(assigned_to=request.user)

    status_filter = (request.GET.get("status") or "all").strip()
    if status_filter in {"pending", "in_progress", "issue", "completed"}:
        qs = qs.filter(status=status_filter)
    else:
        status_filter = "all"

    today = timezone.localdate()
    base_stats = DevelopmentTask.objects.all() if can_assign else DevelopmentTask.objects.filter(assigned_to=request.user)
    stats = {
        "today": base_stats.filter(assigned_date=today).count(),
        "pending": base_stats.filter(status="pending").count(),
        "in_progress": base_stats.filter(status="in_progress").count(),
        "issue": base_stats.filter(status="issue").count(),
        "completed": base_stats.filter(status="completed").count(),
    }

    developers = UserAccount.objects.filter(role="developer", is_active=True).order_by("first_name", "last_name", "email") if can_assign else UserAccount.objects.none()
    projects = Project.objects.order_by("-created_at")[:300] if can_assign else Project.objects.filter(assignments__user=request.user).distinct().order_by("-created_at")[:300]

    task_notifications = list(
        DevelopmentTaskNotification.objects
        .filter(recipient=request.user)
        .select_related("task", "task__project", "actor")
        .order_by("-created_at", "-id")[:20]
    )
    task_notification_unread_count = (
        DevelopmentTaskNotification.objects
        .filter(recipient=request.user, is_read=False)
        .count()
    )

    return render(request, "operations/development_tasks.html", {
        "tasks": qs[:300],
        "stats": stats,
        "status_filter": status_filter,
        "status_choices": DevelopmentTask.STATUS_CHOICES,
        "developers": developers,
        "projects": projects,
        "can_assign": can_assign,
        "today": today,
        "task_notifications": task_notifications,
        "task_notification_unread_count": task_notification_unread_count,
        "active_nav_group": "development",
        "current_page_label": "Tareas",
    })

