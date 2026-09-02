# Gestión de Proyectos 360 · V2

V2 del CRM interno construido sobre **Django + PostgreSQL + Redis + Celery + Docker**. Esta versión reorganiza el sistema alrededor del flujo operativo real de una página web y conserva módulos separados para crecer después hacia software, marketing, dominios y finanzas.

## Flujo principal V2

```text
01 Administración
   └─ crea cliente + selecciona plan web
       ├─ Básica: $1,200
       ├─ Media: $2,400
       └─ Avanzada: $4,000

02 Diseño / Asesoría visual
   └─ reunión con cliente
       ├─ logo
       ├─ estilo de web
       ├─ fondo / colores
       ├─ imágenes / stock
       ├─ servicios
       ├─ paleta HEX
       ├─ degradados
       └─ PDF generado bajo demanda (NO se guarda)

03 Desarrollo
   └─ ficha técnica tipo Excel
       ├─ Estado: Pendiente / Confirmado / No / No aplica
       └─ Respuesta / detalle

04 Resumen de información
   └─ reúne automáticamente
       ├─ datos administrativos
       ├─ plan
       ├─ asesoría visual
       ├─ paleta
       ├─ ficha técnica
       ├─ links de respaldo
       └─ imágenes por categoría

05 Ejecución
   └─ desarrollo, dominio, revisión y entrega
```

## Roles

1. **Global / Gerencia**: acceso total, Finanzas y Usuarios.
2. **Administración**: alta de clientes, selección de plan, clientes y compras de planes.
3. **Marketing**: módulo de marketing y lectura del flujo.
4. **Diseño**: asesoría visual, paletas, PDF, links y referencias de imágenes.
5. **Desarrollador**: ficha técnica, dominios y handoff.

Gerencia atraviesa todos los controles por rol.

## Alta administrativa

La pantalla `Administración > Crear cliente web` solicita:

- Nombre
- Apellido
- ID / identificación opcional
- Teléfono
- Correo opcional
- Nombre de la empresa
- Plan web
- Nota administrativa

Al guardar se crean, en una sola transacción:

- `Client`
- `ClientPlan`
- `Project`

El proyecto queda automáticamente en **Reunión de diseño**.

## Asesoría visual y PDF

El módulo Diseño registra la información del brief visual y una paleta estructurada por roles:

- Texto
- Fondo
- Primario
- Secundario
- Acento
- Extras

También permite degradados. El botón **Descargar PDF** construye el PDF con ReportLab en memoria y lo devuelve directamente al navegador. No existe un `FileField` para el PDF y el archivo no se escribe en `media/`.

## Links e imágenes

Cada proyecto puede tener links externos sin límite rígido:

- Drive de paleta
- Drive de resumen / respaldo
- Logo / identidad
- Banco de fotos
- Documentos
- Otros

Además, se pueden registrar referencias de imágenes con estructura:

```text
Categoría: Roofing
URL: https://...

Categoría: Siding
URL: https://...
```

Esto permite seguir agregando categorías conforme avanza el proyecto.

## Ficha técnica de Desarrollo

La ficha web se basa en el flujo del Excel operativo y en el documento de preguntas. Cada pregunta guarda por separado:

- estado de revisión;
- respuesta o detalle;
- usuario que actualizó;
- fecha de actualización.

Al marcar la ficha como **Completa**, el proyecto pasa a `Información lista` y abre el resumen consolidado.

## Módulos

```text
backend/apps/
├── core
├── accounts
├── administration
├── clients
├── plans
├── projects
├── design
├── questionnaires
├── resources
├── handoff
├── domains
├── marketing
├── finance
├── audit
└── dashboard
```

## Levantar con Docker

En PowerShell:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

O:

```powershell
.\start-local.ps1
```

Abrir:

```text
http://localhost:8000
```

Usuario inicial de desarrollo:

```text
Correo: admin@local.test
Contraseña: Admin12345!
```

Cambiar la contraseña antes de utilizar el sistema fuera de local.

## Primer arranque

El entrypoint ejecuta:

```text
python manage.py check
python manage.py makemigrations ...
python manage.py migrate
python manage.py seed_initial_data
python manage.py bootstrap_manager
python manage.py runserver 0.0.0.0:8000 --noreload
```

Las migraciones siguen generándose al primer arranque porque esta entrega todavía es una **estructura V2 para validar el flujo**. Cuando el flujo quede aprobado, conviene congelar las migraciones y empezar el desarrollo de producción sobre esa base.
