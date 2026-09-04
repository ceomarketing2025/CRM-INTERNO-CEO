from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from apps.core.decorators import role_required
from .forms import MeetingForm, ReminderForm
from .models import Meeting, Reminder
from .services import ensure_meeting_reminder


@role_required("administration", "marketing", "design", "developer")
def reminder_list(request):
    qs = Reminder.objects.select_related("client", "project", "assigned_to").filter(status="pending")
    if not request.user.is_manager:
        qs = qs.filter(Q(assigned_to=request.user) | Q(assigned_to__isnull=True))
    return render(request, "reminders/list.html", {"reminders": qs[:300], "today": timezone.now()})


@role_required("administration", "marketing", "design", "developer")
def reminder_create(request):
    form = ReminderForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False); obj.created_by = request.user; obj.save(); messages.success(request, "Recordatorio creado."); return redirect("reminders:list")
    return render(request, "shared/form.html", {"form": form, "title": "Nuevo recordatorio", "subtitle": "Recordatorio interno asociado a cliente, proyecto o responsable."})


@role_required("administration", "marketing", "design", "developer")
def reminder_done(request, pk):
    obj = get_object_or_404(Reminder, pk=pk)
    if request.method == "POST":
        obj.status = "done"; obj.completed_at = timezone.now(); obj.save(update_fields=["status", "completed_at", "updated_at"]); messages.success(request, "Recordatorio completado.")
    return redirect("reminders:list")


@role_required("administration", "marketing", "design", "developer")
def meeting_list(request):
    qs = Meeting.objects.select_related("client", "project").prefetch_related("attendees")
    return render(request, "reminders/meeting_list.html", {"meetings": qs[:200]})


@role_required("administration", "marketing", "design", "developer")
def meeting_create(request):
    form = MeetingForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False); obj.created_by = request.user; obj.save(); form.save_m2m(); ensure_meeting_reminder(obj, user=request.user); messages.success(request, "Reunión guardada y recordatorio creado."); return redirect("reminders:meeting_list")
    return render(request, "shared/form.html", {"form": form, "title": "Crear reunión / Google Meet", "subtitle": "Registra fecha, participantes y enlace de Meet. El sistema crea el recordatorio interno."})


@role_required("administration", "marketing", "design", "developer")
def meeting_edit(request, pk):
    obj = get_object_or_404(Meeting, pk=pk)
    form = MeetingForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        meeting = form.save()
        ensure_meeting_reminder(meeting, user=request.user)
        messages.success(request, "Reunión y recordatorio actualizados.")
        return redirect("reminders:meeting_list")
    return render(request, "shared/form.html", {"form": form, "title": "Editar reunión", "subtitle": obj.client.business_name})
