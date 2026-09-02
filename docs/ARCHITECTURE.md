# Arquitectura V2

La V2 usa apps Django por dominio funcional y evita concentrar todo en `clients` o `projects`.

- `accounts`: autenticación y cinco roles.
- `administration`: orquesta el alta; no duplica modelos de cliente/plan/proyecto.
- `clients`: ficha maestra del cliente.
- `plans`: catálogo y compra de planes.
- `projects`: estado del flujo y coordinación entre áreas.
- `design`: asesoría visual, paletas, colores, degradados y PDF en memoria.
- `questionnaires`: motor reutilizable para fichas técnicas.
- `resources`: links externos y banco de referencias por categoría.
- `handoff`: resumen derivado y copiable, sin duplicación persistente.
- `domains`: control de registro y renovación de dominios.
- `marketing`: estructura independiente para crecer después.
- `finance`: movimientos internos, solo Gerencia.
- `audit`: trazabilidad de acciones.
- `dashboard`: vista de estado según rol.

## Principio de escalabilidad

Los datos que cambian con frecuencia se modelan de forma dinámica:

- preguntas mediante plantillas/sections/questions;
- categorías de imágenes como texto libre;
- links mediante tipo + área;
- planes mediante catálogo;
- finanzas mediante categorías.

Así, agregar una nueva pregunta, una nueva categoría de fotos o un nuevo plan no requiere rediseñar toda la aplicación.
