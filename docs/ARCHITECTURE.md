# Arquitectura V3

## Módulos principales

- `accounts`: usuarios y 5 roles.
- `clients`: clientes.
- `plans`: planes y compras.
- `projects`: proyecto central + asignaciones por área.
- `administration`: alta administrativa.
- `operations`: Gestión General, Producción y compras de credenciales.
- `reminders`: agenda, reuniones y recordatorios automáticos.
- `design`: brief visual, paletas y PDF temporal.
- `questionnaires`: fichas técnicas dinámicas.
- `marketing`: workspace, checklist, documentos, campañas, Social Media.
- `domains`: dominios.
- `resources`: Drive y referencias de imágenes por categoría.
- `handoff`: Resumen sincronizado.
- `finance`: estructura financiera reservada a Gerencia.
- `audit`: trazabilidad.
- `dashboard`: indicadores por rol.

## Principio de integración

`Project` es el agregado central. Las áreas no cambian el estado de otras áreas. Cada módulo persiste su propia información relacionada con el proyecto/cliente. `handoff.services.build_project_summary()` consulta esas relaciones y crea una vista consolidada.

## Automatización

`reminders.services` crea recordatorios idempotentes mediante `source_key`.

Celery Beat ejecuta:
- Seguimiento diario de planes Social Media.
- Barrido de recordatorios próximos.

Las notificaciones son internas en V3. La arquitectura queda lista para añadir correo/Slack/WhatsApp después sin cambiar modelos de negocio.
