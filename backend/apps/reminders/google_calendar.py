"""Google Calendar / Meet integration for the central CEO Marketing account.

No Google SDK dependency is required. OAuth 2.0 and Calendar API requests use
Python's standard library. OAuth credentials are stored encrypted in the DB.
"""

import base64
import hashlib
import json
import secrets
from datetime import timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils import timezone
from django.db.models import Q

from .models import (
    GoogleCalendarConnection,
    GoogleConnectionStatus,
    GoogleSyncStatus,
    MeetingStatus,
    ReminderCategory,
    ReminderStatus,
)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"
GOOGLE_SCOPES = "openid email https://www.googleapis.com/auth/calendar"


class GoogleCalendarError(RuntimeError):
    pass


def google_auth_configured():
    return bool(
        getattr(settings, "GOOGLE_CALENDAR_CLIENT_ID", "")
        and getattr(settings, "GOOGLE_CALENDAR_CLIENT_SECRET", "")
        and getattr(settings, "GOOGLE_OAUTH_REDIRECT_URI", "")
    )


def get_connection():
    return GoogleCalendarConnection.objects.order_by("id").first()



def calendar_is_connected():
    connection = get_connection()
    return bool(
        google_auth_configured()
        and connection
        and connection.status == GoogleConnectionStatus.CONNECTED
        and connection.encrypted_credentials
    )


def get_or_create_connection():
    obj = get_connection()
    if obj:
        return obj
    return GoogleCalendarConnection.objects.create(
        calendar_id=getattr(settings, "GOOGLE_CALENDAR_ID", "primary") or "primary"
    )


def _fernet():
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _encrypt_credentials(data):
    payload = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return _fernet().encrypt(payload).decode("ascii")


def _decrypt_credentials(value):
    if not value:
        return {}
    try:
        payload = _fernet().decrypt(value.encode("ascii"))
        return json.loads(payload.decode("utf-8"))
    except (InvalidToken, ValueError, json.JSONDecodeError) as exc:
        raise GoogleCalendarError("No se pudieron leer las credenciales Google guardadas.") from exc


def _request_json(url, *, method="GET", data=None, headers=None, timeout=20):
    body = None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    if data is not None:
        if isinstance(data, (dict, list)):
            body = json.dumps(data).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        else:
            body = data
    req = Request(url, data=body, headers=request_headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else {}
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            message = payload.get("error_description") or payload.get("error", {}).get("message") or str(payload)
        except Exception:
            message = str(exc)
        raise GoogleCalendarError(f"Google API: {message}") from exc
    except URLError as exc:
        raise GoogleCalendarError(f"No se pudo conectar con Google: {exc.reason}") from exc


def build_oauth_authorization_url(request):
    if not google_auth_configured():
        raise GoogleCalendarError("Configura GOOGLE_CALENDAR_CLIENT_ID, GOOGLE_CALENDAR_CLIENT_SECRET y GOOGLE_OAUTH_REDIRECT_URI.")
    state = secrets.token_urlsafe(32)
    request.session["google_calendar_oauth_state"] = state
    params = {
        "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def finish_oauth(request, *, code, state, user=None):
    expected_state = request.session.pop("google_calendar_oauth_state", "")
    if not expected_state or not secrets.compare_digest(expected_state, state or ""):
        raise GoogleCalendarError("La validación OAuth no coincide. Intenta conectar Google otra vez.")

    encoded = urlencode(
        {
            "code": code,
            "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
            "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")
    token_data = _request_json(
        GOOGLE_TOKEN_URL,
        method="POST",
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if not token_data.get("access_token"):
        raise GoogleCalendarError("Google no devolvió un token de acceso.")

    credentials = {
        "access_token": token_data["access_token"],
        "refresh_token": token_data.get("refresh_token", ""),
        "token_type": token_data.get("token_type", "Bearer"),
        "scope": token_data.get("scope", GOOGLE_SCOPES),
        "expires_at": (timezone.now() + timedelta(seconds=int(token_data.get("expires_in", 3600)) - 60)).timestamp(),
    }
    userinfo = _request_json(
        GOOGLE_USERINFO_URL,
        headers={"Authorization": f"Bearer {credentials['access_token']}"},
    )
    account_email = (userinfo.get("email") or "").strip().lower()
    expected_email = getattr(settings, "GOOGLE_CALENDAR_ACCOUNT_EMAIL", "").strip().lower()
    if expected_email and account_email and account_email != expected_email:
        raise GoogleCalendarError(
            f"Conectaste {account_email}, pero el CRM espera la cuenta {expected_email}."
        )

    connection = get_or_create_connection()
    connection.account_email = account_email
    connection.calendar_id = getattr(settings, "GOOGLE_CALENDAR_ID", "primary") or "primary"
    connection.encrypted_credentials = _encrypt_credentials(credentials)
    connection.status = GoogleConnectionStatus.CONNECTED
    connection.last_error = ""
    connection.last_synced_at = timezone.now()
    connection.connected_by = user
    connection.save()
    return connection


def disconnect_google_calendar():
    connection = get_connection()
    if not connection:
        return
    connection.encrypted_credentials = ""
    connection.status = GoogleConnectionStatus.DISCONNECTED
    connection.last_error = ""
    connection.save(update_fields=["encrypted_credentials", "status", "last_error", "updated_at"])


def _refresh_credentials(connection, credentials):
    refresh_token = credentials.get("refresh_token")
    if not refresh_token:
        connection.status = GoogleConnectionStatus.ERROR
        connection.last_error = "La autorización no tiene refresh token. Reconecta la cuenta Google."
        connection.save(update_fields=["status", "last_error", "updated_at"])
        raise GoogleCalendarError(connection.last_error)

    encoded = urlencode(
        {
            "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID,
            "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    token_data = _request_json(
        GOOGLE_TOKEN_URL,
        method="POST",
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    credentials["access_token"] = token_data["access_token"]
    credentials["token_type"] = token_data.get("token_type", credentials.get("token_type", "Bearer"))
    credentials["expires_at"] = (timezone.now() + timedelta(seconds=int(token_data.get("expires_in", 3600)) - 60)).timestamp()
    connection.encrypted_credentials = _encrypt_credentials(credentials)
    connection.status = GoogleConnectionStatus.CONNECTED
    connection.last_error = ""
    connection.save(update_fields=["encrypted_credentials", "status", "last_error", "updated_at"])
    return credentials


def get_access_token():
    connection = get_connection()
    if not connection or connection.status != GoogleConnectionStatus.CONNECTED or not connection.encrypted_credentials:
        raise GoogleCalendarError("Google Calendar no está conectado.")
    credentials = _decrypt_credentials(connection.encrypted_credentials)
    if float(credentials.get("expires_at") or 0) <= timezone.now().timestamp():
        credentials = _refresh_credentials(connection, credentials)
    return connection, credentials["access_token"]


def _calendar_request(path, *, method="GET", data=None, params=None):
    connection, token = get_access_token()
    calendar_id = quote(connection.calendar_id or "primary", safe="")
    path = path.format(calendar_id=calendar_id)
    url = f"{GOOGLE_CALENDAR_API}{path}"
    if params:
        url += "?" + urlencode(params)
    return _request_json(
        url,
        method=method,
        data=data,
        headers={"Authorization": f"Bearer {token}"},
    )


def _event_attendees_for_reminder(reminder):
    if not reminder.assigned_to or not reminder.assigned_to.email:
        return []
    connection = get_connection()
    connected_email = (connection.account_email if connection else "").lower()
    email = reminder.assigned_to.email.strip().lower()
    return [] if email == connected_email else [{"email": email}]


def _meeting_attendee_emails(meeting):
    emails = []
    connection = get_connection()
    connected_email = (connection.account_email if connection else "").lower()
    for user in meeting.attendees.all():
        email = (user.email or "").strip().lower()
        if email and email != connected_email and email not in emails:
            emails.append(email)
    raw = meeting.external_attendees or ""
    for token in raw.replace(";", "\n").replace(",", "\n").splitlines():
        email = token.strip().lower()
        if email and email != connected_email and email not in emails:
            emails.append(email)
    return emails


def _calendar_description(*parts):
    return "\n\n".join(str(part).strip() for part in parts if str(part or "").strip())


def sync_reminder_to_google(reminder, *, raise_errors=False):
    """Create/update/delete one Reminder in the central Google Calendar."""
    if reminder.category == ReminderCategory.MEETING:
        # The Meeting itself owns the Calendar event, avoiding duplicates.
        if reminder.google_sync_status != GoogleSyncStatus.SKIPPED:
            reminder.google_sync_status = GoogleSyncStatus.SKIPPED
            reminder.google_sync_error = "La reunión se sincroniza desde el registro Meeting."
            reminder.save(update_fields=["google_sync_status", "google_sync_error", "updated_at"])
        return None

    if not reminder.sync_to_google:
        try:
            if reminder.google_event_id and calendar_is_connected():
                delete_google_event(reminder.google_event_id)
                reminder.google_event_id = ""
                reminder.google_event_url = ""
        except Exception as exc:
            reminder.google_sync_status = GoogleSyncStatus.ERROR
            reminder.google_sync_error = str(exc)[:2000]
            reminder.save()
            if raise_errors:
                raise
            return None
        reminder.google_sync_status = GoogleSyncStatus.SKIPPED
        reminder.google_sync_error = ""
        reminder.google_last_synced_at = timezone.now()
        reminder.save()
        return None

    try:
        if reminder.status == ReminderStatus.CANCELLED:
            if reminder.google_event_id:
                delete_google_event(reminder.google_event_id)
            reminder.google_event_id = ""
            reminder.google_event_url = ""
            reminder.google_sync_status = GoogleSyncStatus.SKIPPED
            reminder.google_sync_error = ""
            reminder.google_last_synced_at = timezone.now()
            reminder.save()
            return None

        end_at = reminder.due_at + timedelta(minutes=30)
        prefix = "✅ " if reminder.status == ReminderStatus.DONE else ""
        description = _calendar_description(
            reminder.notes,
            f"Cliente: {reminder.client.business_name}" if reminder.client else "",
            f"Proyecto: {reminder.project.project_code}" if reminder.project else "",
            f"Responsable: {reminder.assigned_to.display_name}" if reminder.assigned_to else "Equipo",
            "Creado desde CRM CEO Interno · Recordatorios",
        )
        event = {
            "summary": f"{prefix}{reminder.title}",
            "description": description,
            "start": {"dateTime": reminder.due_at.isoformat(), "timeZone": settings.TIME_ZONE},
            "end": {"dateTime": end_at.isoformat(), "timeZone": settings.TIME_ZONE},
            "attendees": _event_attendees_for_reminder(reminder),
            "extendedProperties": {"private": {"crmType": "reminder", "crmId": str(reminder.pk)}},
        }
        send_updates = getattr(settings, "GOOGLE_CALENDAR_SEND_UPDATES", "all")
        if reminder.google_event_id:
            result = _calendar_request(
                "/calendars/{calendar_id}/events/" + quote(reminder.google_event_id, safe=""),
                method="PATCH",
                data=event,
                params={"sendUpdates": send_updates},
            )
        else:
            result = _calendar_request(
                "/calendars/{calendar_id}/events",
                method="POST",
                data=event,
                params={"sendUpdates": send_updates},
            )
        reminder.google_event_id = result.get("id", reminder.google_event_id)
        reminder.google_event_url = result.get("htmlLink", "")
        reminder.google_sync_status = GoogleSyncStatus.SYNCED
        reminder.google_sync_error = ""
        reminder.google_last_synced_at = timezone.now()
        reminder.save()
        return result
    except Exception as exc:
        reminder.google_sync_status = GoogleSyncStatus.ERROR
        reminder.google_sync_error = str(exc)[:2000]
        reminder.save(update_fields=["google_sync_status", "google_sync_error", "updated_at"])
        if raise_errors:
            raise
        return None


def sync_meeting_to_google(meeting, *, raise_errors=False):
    """Create/update a Google Calendar event and optional Google Meet."""
    if not meeting.create_google_event:
        try:
            if meeting.google_event_id and calendar_is_connected():
                delete_google_event(meeting.google_event_id)
                meeting.google_event_id = ""
                meeting.google_event_url = ""
                meeting.meet_url = ""
        except Exception as exc:
            meeting.google_sync_status = GoogleSyncStatus.ERROR
            meeting.google_sync_error = str(exc)[:2000]
            meeting.save()
            if raise_errors:
                raise
            return None
        meeting.google_sync_status = GoogleSyncStatus.SKIPPED
        meeting.google_sync_error = ""
        meeting.google_last_synced_at = timezone.now()
        meeting.save()
        return None

    try:
        if meeting.status == MeetingStatus.CANCELLED:
            if meeting.google_event_id:
                delete_google_event(meeting.google_event_id)
            meeting.google_event_id = ""
            meeting.google_event_url = ""
            meeting.meet_url = ""
            meeting.google_sync_status = GoogleSyncStatus.SKIPPED
            meeting.google_sync_error = ""
            meeting.google_last_synced_at = timezone.now()
            meeting.save()
            return None

        end_at = meeting.scheduled_at + timedelta(minutes=max(meeting.duration_minutes or 60, 5))
        description = _calendar_description(
            meeting.agenda,
            meeting.notes,
            f"Cliente: {meeting.client.business_name}",
            f"Proyecto: {meeting.project.project_code}" if meeting.project else "",
            "Creado desde CRM CEO Interno · Reuniones",
        )
        event = {
            "summary": meeting.title,
            "description": description,
            "start": {"dateTime": meeting.scheduled_at.isoformat(), "timeZone": settings.TIME_ZONE},
            "end": {"dateTime": end_at.isoformat(), "timeZone": settings.TIME_ZONE},
            "attendees": [{"email": email} for email in _meeting_attendee_emails(meeting)],
            "reminders": {
                "useDefault": False,
                "overrides": [{"method": "popup", "minutes": max(meeting.reminder_minutes or 60, 0)}],
            },
            "extendedProperties": {"private": {"crmType": "meeting", "crmId": str(meeting.pk)}},
        }
        if meeting.create_google_meet and not meeting.meet_url:
            event["conferenceData"] = {
                "createRequest": {
                    "requestId": f"crm-meeting-{meeting.pk}-{int(meeting.updated_at.timestamp())}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                }
            }

        params = {
            "sendUpdates": getattr(settings, "GOOGLE_CALENDAR_SEND_UPDATES", "all"),
            "conferenceDataVersion": 1,
        }
        if meeting.google_event_id:
            result = _calendar_request(
                "/calendars/{calendar_id}/events/" + quote(meeting.google_event_id, safe=""),
                method="PATCH",
                data=event,
                params=params,
            )
        else:
            result = _calendar_request(
                "/calendars/{calendar_id}/events",
                method="POST",
                data=event,
                params=params,
            )

        meeting.google_event_id = result.get("id", meeting.google_event_id)
        meeting.google_event_url = result.get("htmlLink", "")
        conference = result.get("conferenceData") or {}
        entry_points = conference.get("entryPoints") or []
        meet_url = next((item.get("uri") for item in entry_points if item.get("entryPointType") == "video"), "")
        meeting.meet_url = meet_url or result.get("hangoutLink", "") or meeting.meet_url
        meeting.google_sync_status = GoogleSyncStatus.SYNCED
        meeting.google_sync_error = ""
        meeting.google_last_synced_at = timezone.now()
        meeting.save()
        return result
    except Exception as exc:
        meeting.google_sync_status = GoogleSyncStatus.ERROR
        meeting.google_sync_error = str(exc)[:2000]
        meeting.save(update_fields=["google_sync_status", "google_sync_error", "updated_at"])
        if raise_errors:
            raise
        return None


def delete_google_event(event_id):
    if not event_id:
        return
    connection, token = get_access_token()
    calendar_id = quote(connection.calendar_id or "primary", safe="")
    url = f"{GOOGLE_CALENDAR_API}/calendars/{calendar_id}/events/{quote(event_id, safe='')}?{urlencode({'sendUpdates': getattr(settings, 'GOOGLE_CALENDAR_SEND_UPDATES', 'all')})}"
    req = Request(url, headers={"Authorization": f"Bearer {token}"}, method="DELETE")
    try:
        with urlopen(req, timeout=20):
            return
    except HTTPError as exc:
        if exc.code in {404, 410}:
            return
        try:
            message = json.loads(exc.read().decode("utf-8")).get("error", {}).get("message", str(exc))
        except Exception:
            message = str(exc)
        raise GoogleCalendarError(f"Google API: {message}") from exc


def list_google_events(*, time_min=None, time_max=None, max_results=50):
    time_min = time_min or timezone.now()
    params = {
        "timeMin": time_min.isoformat(),
        "singleEvents": "true",
        "orderBy": "startTime",
        "maxResults": max_results,
    }
    if time_max:
        params["timeMax"] = time_max.isoformat()
    data = _calendar_request("/calendars/{calendar_id}/events", params=params)
    return data.get("items", [])


def sync_all_pending(*, limit=300):
    from .models import Meeting, Reminder

    results = {"reminders": 0, "meetings": 0, "errors": 0}
    reminders = Reminder.objects.exclude(category=ReminderCategory.MEETING).filter(
        Q(sync_to_google=True) | Q(google_event_id__gt="")
    ).order_by("due_at")[:limit]
    for reminder in reminders:
        before = reminder.google_sync_status
        sync_reminder_to_google(reminder)
        reminder.refresh_from_db(fields=["google_sync_status"])
        if reminder.google_sync_status == GoogleSyncStatus.SYNCED:
            results["reminders"] += 1
        elif reminder.google_sync_status == GoogleSyncStatus.ERROR:
            results["errors"] += 1

    meetings = Meeting.objects.filter(
        Q(create_google_event=True) | Q(google_event_id__gt="")
    ).order_by("scheduled_at")[:limit]
    for meeting in meetings:
        sync_meeting_to_google(meeting)
        meeting.refresh_from_db(fields=["google_sync_status"])
        if meeting.google_sync_status == GoogleSyncStatus.SYNCED:
            results["meetings"] += 1
        elif meeting.google_sync_status == GoogleSyncStatus.ERROR:
            results["errors"] += 1

    connection = get_connection()
    if connection:
        connection.last_synced_at = timezone.now()
        connection.save(update_fields=["last_synced_at", "updated_at"])
    return results
