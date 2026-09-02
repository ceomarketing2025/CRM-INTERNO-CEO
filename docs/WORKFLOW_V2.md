# Flujo operativo V2

## 1. Administración

Responsable: rol `administration` o Gerencia.

Objetivo: registrar únicamente la información mínima necesaria para abrir el proyecto y asociar el plan contratado.

Salida: proyecto web en estado `design_intake`.

## 2. Diseño / Dakmar

Responsable: rol `design` o Gerencia.

Objetivo: completar la asesoría visual del cliente. El modelo permite registrar logo, formato, cambios, estructura visual, dirección de estilo, fondo, imágenes, stock, servicios, tipografía, composición, referencias y cosas a evitar.

La paleta tiene colores clasificados por función y degradados. El PDF se genera al vuelo y no queda almacenado.

Salida: proyecto en `development_intake` y creación automática de la ficha técnica web.

## 3. Desarrollo

Responsable: rol `developer` o Gerencia.

Objetivo: completar el formulario técnico con el patrón utilizado en el Excel: Estado + Respuesta/Detalle.

Estados por pregunta:
- Pendiente
- Confirmado
- No
- No aplica

Salida: al completar la ficha, proyecto en `information_ready`.

## 4. Handoff / Resumen

Disponible para todos los roles autenticados.

No duplica la información en otra tabla: el resumen se genera desde los modelos fuente para evitar versiones desactualizadas.

Incluye botón de copiar para entregar el bloque completo a Desarrollo o cualquier otra área.

## 5. Recursos

`resources` mantiene links y referencias externas separados del brief:

- `ProjectResourceLink`: respaldos de Drive y otros enlaces.
- `ImageReference`: categoría libre + URL de foto/carpeta.

Esto permite crear Roofing, Siding, Gutters, Masonry o cualquier nueva categoría sin migraciones.

## 6. Finanzas

Se conserva como estructura exclusiva de Gerencia. Mantiene categorías para compra de credenciales, dominios, renovaciones, sueldos, costos web, social media, software, hosting, herramientas y otros movimientos.
