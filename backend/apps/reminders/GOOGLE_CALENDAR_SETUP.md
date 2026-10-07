# Google Calendar + Meet · Reminders

La integración usa OAuth 2.0 y Google Calendar API desde la cuenta central de CEO Marketing. No guarda la contraseña de Gmail y no necesita instalar SDKs adicionales de Google.

## 1. Google Cloud

1. Entra a Google Cloud Console con la cuenta que administrará la integración.
2. Crea o selecciona un proyecto para el CRM.
3. Habilita **Google Calendar API**.
4. Configura **OAuth consent screen**.
5. Crea credenciales **OAuth client ID → Web application**.
6. Agrega exactamente esta Authorized redirect URI para desarrollo local:

   `http://localhost:8000/reminders/google/callback/`

7. Si la app OAuth está en modo Testing, agrega la cuenta CEO Marketing como Test user.

## 2. `.env`

Copia estas variables desde `.env.example` al `.env` real:

```env
GOOGLE_CALENDAR_CLIENT_ID=...
GOOGLE_CALENDAR_CLIENT_SECRET=...
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/reminders/google/callback/
GOOGLE_CALENDAR_ACCOUNT_EMAIL=correo-real-de-ceo-marketing@gmail.com
GOOGLE_CALENDAR_ID=primary
GOOGLE_CALENDAR_SEND_UPDATES=all
```

`GOOGLE_CALENDAR_ACCOUNT_EMAIL` es opcional, pero recomendado: evita conectar por accidente otra cuenta Google.

## 3. Migración

```powershell
docker compose exec backend python manage.py migrate reminders
docker compose restart backend celery beat
```

## 4. Conectar cuenta

1. Abre `http://localhost:8000/reminders/`.
2. Entra como Gerencia o Administración.
3. Pulsa **Conectar Google**.
4. Autoriza la cuenta central CEO Marketing.
5. El CRM sincroniza recordatorios y reuniones existentes.

## Comportamiento

- Recordatorio normal: crea/actualiza evento en Calendar.
- Recordatorio completado: el evento se actualiza con `✅`.
- Recordatorio cancelado: elimina el evento Google.
- Reunión: crea evento propio para evitar duplicar el recordatorio interno.
- `Crear Google Meet`: genera automáticamente el enlace Meet.
- Participantes internos: usa su email del CRM como invitado.
- Invitados externos: acepta correos separados por línea, coma o punto y coma.
- Editar fecha/hora/participantes: actualiza el mismo evento, no crea otro.
- Cancelar reunión: elimina el evento Google.
- Celery Beat reintenta sincronización cada 15 minutos.
- Los tokens OAuth se almacenan cifrados en la base de datos mediante `cryptography`.
