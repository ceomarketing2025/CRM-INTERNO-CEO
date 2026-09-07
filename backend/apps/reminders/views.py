import calendar as pycalendar
import hashlib
from collections import defaultdict
from datetime import datetime, time, timedelta
from urllib.parse import urlparse

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.core.decorators import role_required

from .forms import MeetingForm, ReminderForm
from .google_calendar import (
    GoogleCalendarError,
    build_oauth_authorization_url,
    calendar_is_connected,
    disconnect_google_calendar,
    finish_oauth,
    get_connection,
    google_auth_configured,
    list_google_events,
    sync_all_pending,
    sync_meeting_to_google,
    sync_reminder_to_google,
)
from .models import GoogleSyncStatus, Meeting, Reminder, ReminderArea
from .services import ensure_meeting_reminder


ALLOWED_ROLES = ("administration", "marketing", "design", "developer")
PROJECT_COLORS = (
    "#2563eb", "#7c3aed", "#0891b2", "#d97706", "#db2777", "#059669",
    "#4f46e5", "#0f766e", "#9333ea", "#c2410c", "#0369a1", "#65a30d",
)


def _connection_context():
    connection = get_connection()
    return {
        "google_connection": connection,
        "google_configured": google_auth_configured(),
        "google_connected": calendar_is_connected(),
    }


def _manager_or_administration(user):
    return bool(user.is_manager or user.role == "administration")


def _sync_message(request, obj, label):
    if obj.google_sync_status == GoogleSyncStatus.SYNCED:
        extra = ""
        if isinstance(obj, Meeting) and obj.meet_url:
            extra = " Google Meet generado correctamente."
        messages.success(request, f"{label} guardado y sincronizado con Google Calendar.{extra}")
    elif obj.google_sync_status == GoogleSyncStatus.ERROR:
        messages.warning(request, f"{label} guardado, pero Google no sincronizó por completo: {obj.google_sync_error}")
    elif obj.google_sync_status == GoogleSyncStatus.SKIPPED:
        messages.success(request, f"{label} guardado. Sincronización Google desactivada/no aplica.")
    else:
        messages.success(request, f"{label} guardado. Queda pendiente de sincronizar con Google Calendar.")


def _project_color(project=None, client=None):
    if project:
        key = project.pk or project.project_code or project.name
    elif client:
        key = f"client:{client.pk}"
    else:
        return "#64748b"
    digest = hashlib.sha1(str(key).encode("utf-8")).digest()[0]
    return PROJECT_COLORS[digest % len(PROJECT_COLORS)]


def _deadline_meta(value):
    """Estado visual para avisar vencidos y próximos a vencer."""
    if not value:
        return {"state": "normal", "label": ""}
    now = timezone.now()
    local_value = timezone.localtime(value) if timezone.is_aware(value) else value
    local_now = timezone.localtime(now)
    if value < now:
        return {"state": "overdue", "label": "Vencido"}
    if local_value.date() == local_now.date():
        return {"state": "today", "label": "Vence hoy"}
    if value <= now + timedelta(hours=48):
        return {"state": "soon", "label": "Vence pronto"}
    return {"state": "normal", "label": ""}


def _date_deadline_meta(value):
    if not value:
        return {"state": "normal", "label": ""}
    today = timezone.localdate()
    if value < today:
        return {"state": "overdue", "label": "Vencida"}
    if value == today:
        return {"state": "today", "label": "Vence hoy"}
    if value <= today + timedelta(days=2):
        return {"state": "soon", "label": "Vence pronto"}
    return {"state": "normal", "label": ""}


def _decorate_reminder(reminder):
    deadline = _deadline_meta(reminder.due_at)
    reminder.deadline_state = deadline["state"]
    reminder.deadline_label = deadline["label"]
    reminder.project_color = _project_color(reminder.project, reminder.client)
    return reminder


def _decorate_meeting(meeting):
    deadline = _deadline_meta(meeting.scheduled_at) if meeting.status == "scheduled" else {"state": "normal", "label": ""}
    meeting.deadline_state = deadline["state"]
    meeting.deadline_label = deadline["label"]
    meeting.project_color = _project_color(meeting.project, meeting.client)
    return meeting


def _return_target(request, default_name):
    value = (request.GET.get("return_to") or request.POST.get("return_to") or "").strip()
    if value == "marketing_calendar":
        return "reminders:marketing_calendar"
    return default_name


@role_required(*ALLOWED_ROLES)
def reminder_list(request):
    qs = Reminder.objects.select_related("client", "project", "assigned_to").filter(status="pending")
    if not request.user.is_manager:
        qs = qs.filter(Q(assigned_to=request.user) | Q(assigned_to__isnull=True))
    reminders = [_decorate_reminder(item) for item in qs[:300]]
    alert_counts = {
        "overdue": sum(1 for item in reminders if item.deadline_state == "overdue"),
        "today": sum(1 for item in reminders if item.deadline_state == "today"),
        "soon": sum(1 for item in reminders if item.deadline_state == "soon"),
    }
    context = {
        "reminders": reminders,
        "alert_counts": alert_counts,
        "today": timezone.now(),
        **_connection_context(),
    }
    return render(request, "reminders/list.html", context)


@role_required(*ALLOWED_ROLES)
def reminder_create(request):
    initial = {}
    requested_area = request.GET.get("area", "")
    if requested_area in ReminderArea.values:
        initial["area"] = requested_area
    form = ReminderForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.google_sync_status = GoogleSyncStatus.PENDING if obj.sync_to_google else GoogleSyncStatus.SKIPPED
        obj.save()
        if calendar_is_connected():
            sync_reminder_to_google(obj)
            obj.refresh_from_db()
        _sync_message(request, obj, "Recordatorio")
        return redirect(_return_target(request, "reminders:list"))
    return render(
        request,
        "reminders/reminder_form.html",
        {
            "form": form,
            "title": "Nuevo recordatorio",
            "subtitle": "Se sincroniza con la cuenta central de Google Calendar si está conectada.",
            "return_to": request.GET.get("return_to", ""),
            **_connection_context(),
        },
    )


@role_required(*ALLOWED_ROLES)
def reminder_edit(request, pk):
    obj = get_object_or_404(Reminder, pk=pk)
    form = ReminderForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        obj = form.save()
        obj.google_sync_status = GoogleSyncStatus.PENDING if obj.sync_to_google else GoogleSyncStatus.SKIPPED
        obj.google_sync_error = ""
        obj.save(update_fields=["google_sync_status", "google_sync_error", "updated_at"])
        if calendar_is_connected():
            sync_reminder_to_google(obj)
            obj.refresh_from_db()
        _sync_message(request, obj, "Recordatorio")
        return redirect(_return_target(request, "reminders:list"))
    return render(
        request,
        "reminders/reminder_form.html",
        {
            "form": form,
            "title": "Editar recordatorio",
            "subtitle": obj.title,
            "reminder": obj,
            "return_to": request.GET.get("return_to", ""),
            **_connection_context(),
        },
    )


@role_required(*ALLOWED_ROLES)
def reminder_done(request, pk):
    obj = get_object_or_404(Reminder, pk=pk)
    if request.method == "POST":
        obj.status = "done"
        obj.completed_at = timezone.now()
        obj.save(update_fields=["status", "completed_at", "updated_at"])
        if obj.sync_to_google and calendar_is_connected():
            sync_reminder_to_google(obj)
        messages.success(request, "Recordatorio completado.")
    return redirect("reminders:list")


@role_required(*ALLOWED_ROLES)
def reminder_cancel(request, pk):
    obj = get_object_or_404(Reminder, pk=pk)
    if request.method == "POST":
        obj.status = "cancelled"
        obj.save(update_fields=["status", "updated_at"])
        if obj.sync_to_google and calendar_is_connected():
            sync_reminder_to_google(obj)
        messages.success(request, "Recordatorio cancelado.")
    return redirect("reminders:list")


@role_required(*ALLOWED_ROLES)
def reminder_retry_google(request, pk):
    obj = get_object_or_404(Reminder, pk=pk)
    if request.method == "POST":
        if not calendar_is_connected():
            messages.error(request, "Primero conecta la cuenta de Google Calendar.")
        else:
            sync_reminder_to_google(obj)
            obj.refresh_from_db()
            _sync_message(request, obj, "Recordatorio")
    return redirect(request.POST.get("next") or "reminders:list")


@role_required(*ALLOWED_ROLES)
def meeting_list(request):
    qs = Meeting.objects.select_related("client", "project").prefetch_related("attendees")
    meetings = [_decorate_meeting(item) for item in qs[:200]]
    return render(
        request,
        "reminders/meeting_list.html",
        {"meetings": meetings, **_connection_context()},
    )


@role_required(*ALLOWED_ROLES)
def meeting_create(request):
    initial = {}
    requested_area = request.GET.get("area", "")
    if requested_area in ReminderArea.values:
        initial["area"] = requested_area
    form = MeetingForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        # Las reuniones del CRM siempre son Calendar + Meet. Así no existe una
        # reunión "programada" que después quede sin enlace para el cliente.
        obj.create_google_event = True
        obj.create_google_meet = True
        obj.google_sync_status = GoogleSyncStatus.PENDING
        obj.google_sync_error = ""
        obj.save()
        form.save_m2m()
        if calendar_is_connected():
            sync_meeting_to_google(obj)
            obj.refresh_from_db()
        ensure_meeting_reminder(obj, user=request.user)
        _sync_message(request, obj, "Reunión")
        return redirect(_return_target(request, "reminders:meeting_list"))
    return render(
        request,
        "reminders/meeting_form.html",
        {
            "form": form,
            "title": "Asignar reunión",
            "subtitle": "Al guardar se crea Google Calendar + Google Meet automáticamente y se envían las invitaciones.",
            "return_to": request.GET.get("return_to", ""),
            **_connection_context(),
        },
    )


@role_required(*ALLOWED_ROLES)
def meeting_edit(request, pk):
    obj = get_object_or_404(Meeting, pk=pk)
    form = MeetingForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        meeting = form.save(commit=False)
        meeting.create_google_event = True
        meeting.create_google_meet = True
        meeting.google_sync_status = GoogleSyncStatus.PENDING
        meeting.google_sync_error = ""
        meeting.save()
        form.save_m2m()
        if calendar_is_connected():
            sync_meeting_to_google(meeting)
            meeting.refresh_from_db()
        ensure_meeting_reminder(meeting, user=request.user)
        _sync_message(request, meeting, "Reunión")
        return redirect(_return_target(request, "reminders:meeting_list"))
    return render(
        request,
        "reminders/meeting_form.html",
        {
            "form": form,
            "title": "Editar reunión",
            "subtitle": obj.client.business_name,
            "meeting": obj,
            "return_to": request.GET.get("return_to", ""),
            **_connection_context(),
        },
    )


@role_required(*ALLOWED_ROLES)
def meeting_retry_google(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    if request.method == "POST":
        if not calendar_is_connected():
            messages.error(request, "Primero conecta la cuenta de Google Calendar.")
        else:
            meeting.create_google_event = True
            meeting.create_google_meet = True
            meeting.google_sync_status = GoogleSyncStatus.PENDING
            meeting.google_sync_error = ""
            meeting.save(update_fields=["create_google_event", "create_google_meet", "google_sync_status", "google_sync_error", "updated_at"])
            sync_meeting_to_google(meeting)
            meeting.refresh_from_db()
            ensure_meeting_reminder(meeting, user=request.user)
            _sync_message(request, meeting, "Reunión")
    return redirect(request.POST.get("next") or "reminders:meeting_list")


def _month_range(request):
    today = timezone.localdate()
    month_param = request.GET.get("month", "")
    try:
        selected = datetime.strptime(month_param, "%Y-%m").date().replace(day=1) if month_param else today.replace(day=1)
    except ValueError:
        selected = today.replace(day=1)

    if selected.month == 12:
        next_month = selected.replace(year=selected.year + 1, month=1)
    else:
        next_month = selected.replace(month=selected.month + 1)
    if selected.month == 1:
        prev_month = selected.replace(year=selected.year - 1, month=12)
    else:
        prev_month = selected.replace(month=selected.month - 1)

    start_dt = timezone.make_aware(datetime.combine(selected, time.min), timezone.get_current_timezone())
    end_dt = timezone.make_aware(datetime.combine(next_month, time.min), timezone.get_current_timezone())
    return today, selected, prev_month, next_month, start_dt, end_dt


def _calendar_context(request, *, marketing_only=False):
    today, selected, prev_month, next_month, start_dt, end_dt = _month_range(request)

    reminders = Reminder.objects.select_related("client", "project", "assigned_to").filter(
        due_at__gte=start_dt, due_at__lt=end_dt
    ).exclude(status="cancelled")
    meetings = Meeting.objects.select_related("client", "project").filter(
        scheduled_at__gte=start_dt, scheduled_at__lt=end_dt
    ).exclude(status="cancelled")

    if marketing_only:
        reminders = reminders.filter(area=ReminderArea.MARKETING)
        meetings = meetings.filter(area=ReminderArea.MARKETING)

    day_items = defaultdict(list)
    project_legend = {}
    warning_counts = {"overdue": 0, "today": 0, "soon": 0}

    for reminder in reminders:
        local = timezone.localtime(reminder.due_at)
        deadline = _deadline_meta(reminder.due_at) if reminder.status == "pending" else {"state": "normal", "label": ""}
        color = _project_color(reminder.project, reminder.client)
        if deadline["state"] in warning_counts:
            warning_counts[deadline["state"]] += 1
        if reminder.project:
            project_legend[reminder.project_id] = {
                "label": f"{reminder.project.project_code} · {reminder.project.client.business_name}",
                "color": color,
            }
        day_items[local.date()].append({
            "kind": "reminder", "time": local, "obj": reminder, "color": color,
            "deadline_state": deadline["state"], "deadline_label": deadline["label"],
        })

    for meeting in meetings:
        local = timezone.localtime(meeting.scheduled_at)
        deadline = _deadline_meta(meeting.scheduled_at) if meeting.status == "scheduled" else {"state": "normal", "label": ""}
        color = _project_color(meeting.project, meeting.client)
        if deadline["state"] in warning_counts:
            warning_counts[deadline["state"]] += 1
        if meeting.project:
            project_legend[meeting.project_id] = {
                "label": f"{meeting.project.project_code} · {meeting.project.client.business_name}",
                "color": color,
            }
        day_items[local.date()].append({
            "kind": "meeting", "time": local, "obj": meeting, "color": color,
            "deadline_state": deadline["state"], "deadline_label": deadline["label"],
        })

    marketing_tasks = []
    if marketing_only:
        try:
            from apps.marketing.models import MarketingTask
            marketing_tasks = MarketingTask.objects.select_related("project", "project__client", "assigned_to").filter(
                due_date__gte=selected,
                due_date__lt=next_month,
            ).exclude(status="done")
            for task in marketing_tasks:
                color = _project_color(task.project, task.project.client if task.project else None)
                deadline = _date_deadline_meta(task.due_date)
                if deadline["state"] in warning_counts:
                    warning_counts[deadline["state"]] += 1
                if task.project:
                    project_legend[task.project_id] = {
                        "label": f"{task.project.project_code} · {task.project.client.business_name}",
                        "color": color,
                    }
                task_time = timezone.make_aware(
                    datetime.combine(task.due_date, time(hour=9)),
                    timezone.get_current_timezone(),
                )
                day_items[task.due_date].append({
                    "kind": "marketing_task", "time": task_time, "obj": task, "color": color,
                    "deadline_state": deadline["state"], "deadline_label": deadline["label"],
                })
        except Exception:
            # El calendario de Reminders debe seguir funcionando aunque Marketing
            # esté temporalmente en una migración/versión diferente.
            marketing_tasks = []

    for values in day_items.values():
        values.sort(key=lambda item: item["time"])

    cal = pycalendar.Calendar(firstweekday=0)
    weeks = []
    for week in cal.monthdatescalendar(selected.year, selected.month):
        weeks.append([
            {"date": day, "in_month": day.month == selected.month, "items": day_items.get(day, [])}
            for day in week
        ])

    google_events = []
    google_error = ""
    if not marketing_only and calendar_is_connected():
        try:
            raw_events = list_google_events(time_min=start_dt, time_max=end_dt, max_results=100)
            for event in raw_events:
                private = ((event.get("extendedProperties") or {}).get("private") or {})
                if private.get("crmType") in {"reminder", "meeting"}:
                    continue
                start_value = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date")
                start_obj = parse_datetime(start_value) if "T" in (start_value or "") else parse_date(start_value or "")
                google_events.append({
                    "summary": event.get("summary") or "Evento Google",
                    "start": start_obj,
                    "html_link": event.get("htmlLink", ""),
                    "meet_url": event.get("hangoutLink", ""),
                })
        except GoogleCalendarError as exc:
            google_error = str(exc)

    context = {
        "weeks": weeks,
        "selected_month": selected,
        "prev_month": prev_month.strftime("%Y-%m"),
        "next_month": next_month.strftime("%Y-%m"),
        "today": today,
        "google_events": google_events,
        "google_error": google_error,
        "project_legend": list(project_legend.values()),
        "warning_counts": warning_counts,
        "marketing_only": marketing_only,
        "calendar_url_name": "reminders:marketing_calendar" if marketing_only else "reminders:calendar",
        **_connection_context(),
    }
    if marketing_only:
        context.update({
            "active_nav_group": "marketing",
            "current_module_label": "Marketing",
            "current_page_label": "Calendario Marketing",
            "current_namespace": "reminders",
            "current_url_name": "marketing_calendar",
        })
    return context


@role_required(*ALLOWED_ROLES)
def calendar_view(request):
    return render(request, "reminders/calendar.html", _calendar_context(request, marketing_only=False))


@role_required("marketing")
def marketing_calendar_view(request):
    return render(request, "reminders/calendar.html", _calendar_context(request, marketing_only=True))


@role_required("administration")
def google_connect(request):
    if not _manager_or_administration(request.user):
        raise PermissionDenied("Solo Gerencia/Administración puede conectar la cuenta central de Google.")

    configured_redirect = getattr(__import__("django.conf", fromlist=["settings"]).settings, "GOOGLE_OAUTH_REDIRECT_URI", "")
    redirect_host = (urlparse(configured_redirect).hostname or "").lower()
    request_host = request.get_host().split(":", 1)[0].lower()
    if redirect_host in {"localhost", "127.0.0.1"} and request_host not in {"localhost", "127.0.0.1"}:
        messages.warning(
            request,
            "Para conectar la cuenta Google en desarrollo, abre este CRM desde http://localhost:8000 y vuelve a pulsar Conectar Google. "
            "Después de conectarla, el resto del equipo puede seguir usando el CRM por la IP local.",
        )
        return redirect("reminders:list")

    try:
        return redirect(build_oauth_authorization_url(request))
    except GoogleCalendarError as exc:
        messages.error(request, str(exc))
        return redirect("reminders:list")


@role_required("administration")
def google_callback(request):
    if not _manager_or_administration(request.user):
        raise PermissionDenied("Solo Gerencia/Administración puede conectar la cuenta central de Google.")
    if request.GET.get("error"):
        messages.error(request, f"Google canceló la autorización: {request.GET.get('error')}")
        return redirect("reminders:list")

    try:
        connection = finish_oauth(
            request,
            code=request.GET.get("code", ""),
            state=request.GET.get("state", ""),
            user=request.user,
        )

        queued = False
        try:
            from .tasks import sync_google_calendar
            sync_google_calendar.delay()
            queued = True
        except Exception:
            queued = False

        if queued:
            detail = "La sincronización inicial se está ejecutando en segundo plano."
        else:
            detail = "La cuenta quedó conectada. Usa ‘Sincronizar ahora’ para procesar los eventos pendientes."

        messages.success(
            request,
            f"Google Calendar conectado con {connection.account_email or 'la cuenta autorizada'}. {detail}",
        )
    except GoogleCalendarError as exc:
        messages.error(request, str(exc))
    return redirect("reminders:list")


@role_required("administration")
def google_disconnect(request):
    if request.method == "POST":
        disconnect_google_calendar()
        messages.success(request, "Cuenta Google desconectada del CRM. Los eventos ya creados permanecen en Calendar.")
    return redirect("reminders:list")


@role_required("administration")
def google_sync_now(request):
    if request.method == "POST":
        if not calendar_is_connected():
            messages.error(request, "Primero conecta la cuenta de Google Calendar.")
        else:
            results = sync_all_pending(limit=500)
            if results["errors"]:
                messages.warning(
                    request,
                    f"Sincronización terminada con {results['errors']} errores. Revisa los elementos marcados en rojo.",
                )
            else:
                messages.success(
                    request,
                    f"Sincronización completa: {results['reminders']} recordatorios y {results['meetings']} reuniones.",
                )
    return redirect(request.POST.get("next") or "reminders:list")
