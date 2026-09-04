import calendar as pycalendar
from collections import defaultdict
from datetime import datetime, time, timedelta

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
from .models import GoogleSyncStatus, Meeting, Reminder
from .services import ensure_meeting_reminder


ALLOWED_ROLES = ("administration", "marketing", "design", "developer")


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
        messages.success(request, f"{label} guardado y sincronizado con Google Calendar.")
    elif obj.google_sync_status == GoogleSyncStatus.ERROR:
        messages.warning(request, f"{label} guardado, pero Google no sincronizó: {obj.google_sync_error}")
    elif obj.google_sync_status == GoogleSyncStatus.SKIPPED:
        messages.success(request, f"{label} guardado. Sincronización Google desactivada/no aplica.")
    else:
        messages.success(request, f"{label} guardado. Queda pendiente de sincronizar con Google Calendar.")


@role_required(*ALLOWED_ROLES)
def reminder_list(request):
    qs = Reminder.objects.select_related("client", "project", "assigned_to").filter(status="pending")
    if not request.user.is_manager:
        qs = qs.filter(Q(assigned_to=request.user) | Q(assigned_to__isnull=True))
    context = {
        "reminders": qs[:300],
        "today": timezone.now(),
        **_connection_context(),
    }
    return render(request, "reminders/list.html", context)


@role_required(*ALLOWED_ROLES)
def reminder_create(request):
    form = ReminderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.google_sync_status = GoogleSyncStatus.PENDING if obj.sync_to_google else GoogleSyncStatus.SKIPPED
        obj.save()
        if calendar_is_connected():
            sync_reminder_to_google(obj)
            obj.refresh_from_db()
        _sync_message(request, obj, "Recordatorio")
        return redirect("reminders:list")
    return render(
        request,
        "reminders/reminder_form.html",
        {"form": form, "title": "Nuevo recordatorio", "subtitle": "Se sincroniza con la cuenta central de Google Calendar si está conectada.", **_connection_context()},
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
        return redirect("reminders:list")
    return render(
        request,
        "reminders/reminder_form.html",
        {"form": form, "title": "Editar recordatorio", "subtitle": obj.title, "reminder": obj, **_connection_context()},
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
    return render(
        request,
        "reminders/meeting_list.html",
        {"meetings": qs[:200], **_connection_context()},
    )


@role_required(*ALLOWED_ROLES)
def meeting_create(request):
    form = MeetingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        obj.created_by = request.user
        obj.google_sync_status = GoogleSyncStatus.PENDING if obj.create_google_event else GoogleSyncStatus.SKIPPED
        obj.save()
        form.save_m2m()
        if calendar_is_connected():
            sync_meeting_to_google(obj)
            obj.refresh_from_db()
        ensure_meeting_reminder(obj, user=request.user)
        _sync_message(request, obj, "Reunión")
        return redirect("reminders:meeting_list")
    return render(
        request,
        "reminders/meeting_form.html",
        {"form": form, "title": "Asignar reunión", "subtitle": "Crea el evento en Google Calendar, genera Meet e invita participantes.", **_connection_context()},
    )


@role_required(*ALLOWED_ROLES)
def meeting_edit(request, pk):
    obj = get_object_or_404(Meeting, pk=pk)
    form = MeetingForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        meeting = form.save()
        meeting.google_sync_status = GoogleSyncStatus.PENDING if meeting.create_google_event else GoogleSyncStatus.SKIPPED
        meeting.google_sync_error = ""
        meeting.save(update_fields=["google_sync_status", "google_sync_error", "updated_at"])
        if calendar_is_connected():
            sync_meeting_to_google(meeting)
            meeting.refresh_from_db()
        ensure_meeting_reminder(meeting, user=request.user)
        _sync_message(request, meeting, "Reunión")
        return redirect("reminders:meeting_list")
    return render(
        request,
        "reminders/meeting_form.html",
        {"form": form, "title": "Editar reunión", "subtitle": obj.client.business_name, "meeting": obj, **_connection_context()},
    )


@role_required(*ALLOWED_ROLES)
def meeting_retry_google(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)
    if request.method == "POST":
        if not calendar_is_connected():
            messages.error(request, "Primero conecta la cuenta de Google Calendar.")
        else:
            sync_meeting_to_google(meeting)
            meeting.refresh_from_db()
            ensure_meeting_reminder(meeting, user=request.user)
            _sync_message(request, meeting, "Reunión")
    return redirect(request.POST.get("next") or "reminders:meeting_list")


@role_required(*ALLOWED_ROLES)
def calendar_view(request):
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

    reminders = Reminder.objects.select_related("client", "assigned_to").filter(
        due_at__gte=start_dt, due_at__lt=end_dt
    ).exclude(status="cancelled")
    meetings = Meeting.objects.select_related("client", "project").filter(
        scheduled_at__gte=start_dt, scheduled_at__lt=end_dt
    ).exclude(status="cancelled")

    day_items = defaultdict(list)
    for reminder in reminders:
        local = timezone.localtime(reminder.due_at)
        day_items[local.date()].append({"kind": "reminder", "time": local, "obj": reminder})
    for meeting in meetings:
        local = timezone.localtime(meeting.scheduled_at)
        day_items[local.date()].append({"kind": "meeting", "time": local, "obj": meeting})
    for values in day_items.values():
        values.sort(key=lambda item: item["time"])

    cal = pycalendar.Calendar(firstweekday=0)
    weeks = []
    for week in cal.monthdatescalendar(selected.year, selected.month):
        weeks.append([{"date": day, "in_month": day.month == selected.month, "items": day_items.get(day, [])} for day in week])

    google_events = []
    google_error = ""
    if calendar_is_connected():
        try:
            raw_events = list_google_events(time_min=start_dt, time_max=end_dt, max_results=100)
            for event in raw_events:
                private = ((event.get("extendedProperties") or {}).get("private") or {})
                if private.get("crmType") in {"reminder", "meeting"}:
                    continue
                start_value = (event.get("start") or {}).get("dateTime") or (event.get("start") or {}).get("date")
                start_obj = parse_datetime(start_value) if "T" in (start_value or "") else parse_date(start_value or "")
                google_events.append(
                    {
                        "summary": event.get("summary") or "Evento Google",
                        "start": start_obj,
                        "html_link": event.get("htmlLink", ""),
                        "meet_url": event.get("hangoutLink", ""),
                    }
                )
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
        **_connection_context(),
    }
    return render(request, "reminders/calendar.html", context)


@role_required("administration")
def google_connect(request):
    if not _manager_or_administration(request.user):
        raise PermissionDenied("Solo Gerencia/Administración puede conectar la cuenta central de Google.")
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
        results = sync_all_pending(limit=300)
        messages.success(
            request,
            f"Google Calendar conectado con {connection.account_email or 'la cuenta autorizada'}. "
            f"Sincronizados: {results['reminders']} recordatorios y {results['meetings']} reuniones.",
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
