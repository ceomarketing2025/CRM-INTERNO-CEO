# CRM CEO Interno · V3

Sistema interno Django + PostgreSQL + Redis/Celery para centralizar clientes, planes, Diseño, Marketing, Desarrollo, Producción, compras/credenciales, reuniones y recordatorios.

## Cambio principal de V3

V3 **elimina el flujo rígido entre áreas**. Administración crea el cliente/proyecto y Gerencia asigna responsables. Diseño, Marketing y Desarrollo pueden trabajar en paralelo sobre el mismo proyecto. El módulo **Resumen sincronizado** consolida la información de todas las áreas.

## Roles

- **Global / Gerencia**: acceso completo, usuarios, finanzas y todas las áreas.
- **Administración**: altas de clientes, planes, Gestión General, Producción, credenciales, reuniones y control administrativo.
- **Marketing**: workspace del cliente, Google Business, documentos PDF/Drive, Ads, LSA/Guarantee, campañas y Social Media.
- **Diseño**: asesoría visual, paletas, degradados y generación temporal del PDF de paleta.
- **Desarrollador**: ficha técnica, información de desarrollo, dominios y ejecución técnica de proyectos asignados.

## Administración

### Alta de cliente
Registra:
- Nombre / apellido
- ID opcional
- Teléfono / correo
- Empresa
- Plan Web: Básica $1,200 / Media $2,400 / Avanzada $4,000
- Fecha de inicio

Al guardar se crean:
- Cliente
- Compra del plan
- Proyecto activo
- Recordatorio a 6 semanas
- Recordatorio para ofrecer Social Media a las 3 semanas

### Gestión General
Replica la hoja operativa con:
`E · Fecha · Mes · Cliente · Nombre/Detalle · Tipo Servicio · Proveedor · Costo · Moneda · Estado · Link Recibo Drive · Responsable · Notas`

Tipos de servicio: Dominio y Host, Dominio, Host, Mensualidades, Credenciales, Google Guarantee, Google Business Profile, Ads y Otros.

Proveedores: GoDaddy, Namecheap, Hostinger, SiteGround, Google, Meta, YouTube y Other.

### Producción
Campos:
`Cliente · Referencia · Proyecto/Sitio · Inicio plan · Diseño · Estado Tec · Estado · Colaborador · Notas · Costo · Anticipo · Pendiente · Web final`

Estado de Producción: `terminado · entregado · pendiente pago · pendiente web · iniciar`.

Colaborador usa usuarios del rol Desarrollador/Global, no nombres rígidos.

### Credenciales
Registra la compra sin guardar contraseñas. Si no se indica otra fecha, calcula renovación a un año y crea recordatorio automático.

## Reuniones y recordatorios

- Reuniones con fecha, cliente, proyecto, participantes, agenda y enlace Google Meet.
- Control a 6 semanas.
- Renovación anual de credenciales.
- Seguimiento 15 días después del lanzamiento para Administración + Marketing asignado.
- Seguimiento reviews / Google Guarantee.
- Ofrecer Social Media a las 3 semanas.
- Informe mensual de Social Media.
- Revisión de Gerencia antes de lanzar campañas.
- Seguimiento semanal durante la duración de campañas.
- Seguimiento diario para planes Social Media mediante Celery Beat.

## Marketing

Cada proyecto tiene un **Marketing Workspace** con:
- Datos de reunión
- Dueño y nombre legal
- Fecha de fundación
- Redes sociales
- Descripción
- Horario
- Servicios / áreas
- Gmail
- Estado Google Business: no iniciado / verificación / aprobado / desaprobado
- Link Google Business
- Link de reviews
- Mensaje para clientes
- Documentos disponibles Sí/No
- Verificación Google Ads / LSA / Google Guarantee
- Documentos PDF o links Drive

### Checklist Marketing
Incluye checklists para:
- Recolección de datos y documentos
- Google Business Profile
- Google LSA / Guarantee
- Meta Ads
- Google Ads
- Social Media

Los checks usan **Completo / Incompleto** y un campo opcional **Sí / No**.

Cuando Marketing marca **Crear Google Business Profile = Completo**, el sistema genera un recordatorio para Administración para comprar/registrar credenciales.

Si existe un link de reviews, se puede descargar un **QR generado al vuelo**; el PNG no se guarda como archivo permanente.

### Campañas
Meta Ads, Google Ads o Pauta tradicional. Campos de cuenta, objetivo, tipo, keywords/estudio, artes, revisión Gerencia, fechas y estado. Al lanzar una campaña se crean recordatorios semanales hasta su fecha final.

### Seguimiento Social Media / Google
Tabla con estados simples:
- Reseñas
- Productos
- Porcentaje de perfil
- GB
- Redes
- Website en GB
- Último Post GB
- Notas GB
- LSA
- Fotos
- Último Lead
- Ads verificado
- Seguimiento con Google Sí/No
- Notas

### Plan Social Media
Seguimiento diario de publicación + gestión y revisión/informe mensual.

## Diseño

Mantiene la asesoría visual, paletas por código HEX, degradados y links de respaldo. El PDF de paleta se genera en memoria para descarga y **no se guarda en la base ni en disco**.

## Desarrollo

La ficha técnica Web conserva la lógica del Excel: Estado + Respuesta/Detalle y bloque preparado para copiar. Desarrollo puede empezar aunque Diseño o Marketing todavía no hayan terminado.

## Resumen sincronizado

Por proyecto reúne:
- Administración
- Diseño + paleta
- Marketing + checklist
- Desarrollo / cuestionarios
- Producción
- Credenciales / renovaciones (sin contraseñas/costos sensibles)
- Campañas
- Seguimiento Social / Google
- Links Drive
- Imágenes por categoría
- Recordatorios pendientes

Incluye botón **Copiar todo**.

## Levantar con Docker

```powershell
cd "C:\Users\Lenovo\Downloads\CRM-Gestion-360-V3"
Copy-Item .env.example .env
docker compose down
docker compose up --build
```

Abrir: `http://localhost:8000`

Usuario bootstrap por defecto (solo desarrollo local):
- `admin@local.test`
- `Admin12345!`

Cámbialo antes de producción.

## Servicios Docker

- `backend`: Django
- `db`: PostgreSQL 16
- `redis`: Redis 7
- `celery`: worker
- `beat`: recordatorios/tareas periódicas

## Seguridad

- No guardar contraseñas de terceros dentro del CRM.
- `CredentialPurchase` guarda solo correo/usuario de referencia y un link seguro opcional.
- Documentos de Marketing deben servirse de forma privada en producción; no exponer `/media/` directamente con Nginx.
- Cambiar `SECRET_KEY`, contraseña bootstrap y `DEBUG=False` antes de desplegar.
