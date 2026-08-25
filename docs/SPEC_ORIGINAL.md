```markdown
# Automatización de Facturas y Documentos – Spec Técnica

## 1. Objetivo

Sistema self-hosted que:

- Monitoriza la bandeja de Gmail de la empresa.
- Aplica etiquetas automáticamente según tipo de correo.
- Descarga y procesa adjuntos (PDF suelto, ZIP con PDF + archivo X, notas de crédito, etc.).
- Identifica y extrae metadatos de facturas/documentos.
- Almacena archivos + metadatos de forma estructurada.
- Expone un dashboard web para control y consulta por parte de los usuarios finales (padres).

**No se usan plataformas de automatización de terceros** (Make, Zapier, n8n cloud, etc.). Todo código propio + infraestructura controlada.

---

## 2. Constraints

- Email source: Gmail (API oficial).
- Sin dependencias de SaaS de automatización.
- Debe soportar múltiples formatos de llegada:
  - PDF suelto
  - ZIP conteniendo PDF + archivo X (normalmente XML)
  - Notas de crédito
  - Correos sin adjunto o solo con enlaces
  - Ruido (invitaciones a foros, newsletters, etc.)
- Extracción de datos debe ser robusta ante variaciones de emisor.
- El dashboard debe ser usable por personas no técnicas.
- Todo el procesamiento debe ser auditable (logs de cada correo procesado).

---

## 3. Arquitectura de alto nivel

```
Gmail API
    ↓ (polling o push via Pub/Sub)
Ingestion Worker
    ↓
Attachment Downloader + ZIP Extractor
    ↓
Classifier + Metadata Extractor
    ↓
File Storage (FS / MinIO)
    ↓
PostgreSQL (metadatos + estado)
    ↓
API Backend (FastAPI)
    ↓
Dashboard Frontend (React/Next.js)
```

Componentes principales:

1. **Ingestion Service** – obtiene correos nuevos / no procesados.
2. **Processor Pipeline** – descarga, descomprime, clasifica, extrae.
3. **Label Manager** – aplica/elimina etiquetas en Gmail.
4. **Storage Layer** – archivos + base de datos.
5. **API + Dashboard** – consulta, filtros, descarga, marcado de estado.

---

## 4. Stack recomendado

| Capa              | Tecnología                          | Notas |
|-------------------|-------------------------------------|-------|
| Runtime           | Python 3.12+                        | Mejor ecosistema para PDF/XML |
| Backend API       | FastAPI                             | Async, tipado, OpenAPI automático |
| Worker / Queue    | Celery + Redis o RQ                 | Procesamiento asíncrono |
| DB                | PostgreSQL 16                       | Metadatos + full-text search |
| File Storage      | Local FS (producción) o MinIO       | Estructura por año/mes |
| Gmail             | google-api-python-client + OAuth2   | Service Account con domain-wide delegation o OAuth usuario |
| PDF               | pypdf + pdfplumber                  | Texto + tablas |
| XML               | lxml + schemas propios              | Facturae / UBL / genérico |
| Frontend          | Next.js 15 + Tailwind + shadcn/ui   | SSR + client components |
| Auth Dashboard    | NextAuth.js (Google OAuth) o JWT simple | Acceso restringido |
| Deploy            | Docker Compose + Caddy/Nginx        | Self-hosted |
| Observability     | structlog + Prometheus + Grafana    | Opcional pero recomendado |

---

## 5. Modelo de datos (PostgreSQL)

### Tabla `emails`
```sql
id              UUID PK
gmail_id        TEXT UNIQUE NOT NULL
thread_id       TEXT
subject         TEXT
from_address    TEXT
received_at     TIMESTAMPTZ
raw_headers     JSONB
body_plain      TEXT
body_html       TEXT
labels          TEXT[]
processing_status  ENUM('pending','processing','processed','failed','ignored')
error_message   TEXT
created_at      TIMESTAMPTZ
updated_at      TIMESTAMPTZ
```

### Tabla `documents`
```sql
id              UUID PK
email_id        UUID FK → emails
type            ENUM('invoice','credit_note','other','unknown')
file_path       TEXT NOT NULL          -- ruta relativa en storage
original_filename TEXT
mime_type       TEXT
file_hash       TEXT                  -- SHA-256
extracted_data  JSONB                 -- nº factura, fecha, importe, emisor, etc.
confidence      FLOAT
is_zip_member   BOOLEAN DEFAULT FALSE
parent_zip_id   UUID NULL
created_at      TIMESTAMPTZ
```

### Tabla `extracted_fields` (opcional, normalizado)
```sql
id              UUID PK
document_id     UUID FK
field_name      TEXT                  -- invoice_number, issue_date, total_amount, supplier_nif, etc.
field_value     TEXT
raw_value       TEXT
confidence      FLOAT
```

### Índices críticos
- `emails(gmail_id)`
- `emails(received_at)`
- `documents(type, extracted_data->>'invoice_number')`
- GIN en `extracted_data` y `labels`

---

## 6. Pipeline de procesamiento (orden exacto)

1. **Fetch**
   - Polling cada X minutos o Gmail Push (Pub/Sub) → mensaje con `historyId`.
   - Obtener solo mensajes con `labelIds` que no contengan `PROCESSED` ni `IGNORED`.

2. **Persistencia inicial**
   - Insertar registro en `emails` con status `pending`.
   - Guardar headers + body.

3. **Descarga de adjuntos**
   - Si no hay adjuntos → clasificar como posible ruido o correo informativo.
   - Si hay `.zip` → descargar y extraer en memoria o temp dir.
   - Identificar miembros: PDF, XML/X, otros.

4. **Clasificación de tipo de documento**
   - Reglas deterministas primero:
     - Nombre de archivo + extensión
     - MIME type
     - Presencia de XML con namespace Facturae / UBL / CFDI
     - Keywords en subject/body (`factura`, `nota de crédito`, `credit note`, etc.)
   - Fallback: extracción de texto del PDF + reglas / ML ligero / LLM local si se decide.

5. **Extracción de metadatos**
   - PDF → pdfplumber + regex / invoice2data-like rules + posibles coordenadas.
   - XML → parse con lxml según schema detectado.
   - Normalizar campos: `invoice_number`, `issue_date`, `due_date`, `total`, `tax`, `supplier_name`, `supplier_tax_id`, `customer_tax_id`, `currency`.

6. **Storage de archivos**
   - Path canónico: `{year}/{month}/{yyyy-mm-dd}_{supplier_slug}_{invoice_number}.{ext}`
   - Guardar hash SHA-256 para deduplicación.
   - Si viene de ZIP, guardar tanto el ZIP original como los miembros extraídos (o solo los miembros + referencia).

7. **Actualización de Gmail**
   - Añadir etiqueta según resultado (`INVOICE`, `CREDIT_NOTE`, `OTHER_DOC`, `NOISE`).
   - Añadir etiqueta `PROCESSED`.
   - Opcional: mover a carpeta / archivar.

8. **Marcar como procesado**
   - Actualizar `processing_status = 'processed'`.
   - Si falla → `failed` + log detallado + reintento con backoff.

---

## 7. Manejo específico de formatos

### PDF suelto
- Extraer texto + tablas.
- Intentar localizar bloque de cabecera (NIF, número, fecha).

### ZIP (PDF + X)
- Listar contenido.
- Priorizar XML si existe (más estructurado).
- Si el XML es válido según schema conocido → usar XML como source of truth.
- PDF se guarda igualmente para visualización humana.

### Notas de crédito
- Detectar por keywords + importe negativo o campo específico en XML.
- Tipo `credit_note`.

### Ruido
- Listas blancas/negras de remitentes.
- Asuntos que contengan “foro”, “newsletter”, “invitación”, “webinar”, etc.
- Correos sin adjuntos relevantes y sin keywords de factura → `ignored`.

---

## 8. Gmail Labels (convención)

Crear y mantener estas etiquetas vía API:

- `AUTO/PENDING`
- `AUTO/PROCESSED`
- `AUTO/INVOICE`
- `AUTO/CREDIT_NOTE`
- `AUTO/OTHER`
- `AUTO/NOISE`
- `AUTO/FAILED`

El sistema nunca borra correos. Solo etiqueta y opcionalmente archiva.

---

## 9. Dashboard (requisitos funcionales)

### Vistas principales
- Listado de documentos con filtros:
  - Rango de fechas
  - Tipo (factura / nota de crédito / otro)
  - Proveedor
  - Estado de procesamiento
  - Importe
  - Texto libre (nº factura, NIF, etc.)
- Detalle de documento:
  - Metadatos extraídos (editables manualmente)
  - Preview del PDF
  - Descarga original + miembros del ZIP
  - Correo de origen (enlace a Gmail)
  - Historial de cambios de estado
- Acciones:
  - Marcar como “Revisada”
  - Marcar como “Pagada”
  - Corregir metadatos
  - Reprocesar
  - Descargar lote (ZIP)

### UX mínima
- Responsive.
- Búsqueda rápida.
- Export CSV / Excel de la vista filtrada.
- Indicador visual de correos fallidos.

---

## 10. Orden de implementación (backlog técnico)

### Fase 0 – Fundamentos
1. Repo + estructura monorepo o multi-repo (backend / worker / frontend).
2. Docker Compose: PostgreSQL + Redis + MinIO (opcional) + mailhog para tests.
3. Configuración de Gmail API (credenciales, scopes, token refresh).
4. Modelo de datos + migraciones (Alembic).
5. Logging estructurado + healthchecks.

### Fase 1 – Ingestion básica
6. Servicio que lista mensajes nuevos vía `users.messages.list` + `get`.
7. Persistencia de email crudo en `emails`.
8. Descarga de adjuntos a storage temporal.
9. Detección y extracción de ZIPs.
10. Aplicación de etiquetas `AUTO/PENDING` y `AUTO/PROCESSED`.

### Fase 2 – Clasificación y extracción
11. Motor de reglas de clasificación (PDF / ZIP / XML / ruido).
12. Parser XML (empezar por el schema más común que tengan).
13. Extracción de texto de PDF + reglas de campos clave.
14. Normalización de datos y escritura en `documents` + `extracted_data`.
15. Deduplicación por hash + número de factura + emisor.

### Fase 3 – API
16. FastAPI: endpoints CRUD de documentos y emails.
17. Filtros, paginación, ordenación.
18. Endpoint de descarga de archivo (con auth).
19. Endpoint de reprocesado manual.
20. Auth (JWT o Google OAuth).

### Fase 4 – Frontend
21. Next.js app con listado + filtros.
22. Página de detalle con preview PDF.
23. Acciones de estado (revisada / pagada).
24. Corrección manual de metadatos.
25. Exportación.

### Fase 5 – Robustez
26. Reintentos con exponential backoff.
27. Dead letter queue / tabla de fallos.
28. Alertas (email o webhook) cuando hay `failed` consecutivos.
29. Tests de integración con fixtures reales de correos (PDF, ZIP, XML).
30. Documentación de despliegue y runbook.

---

## 11. Seguridad y operaciones

- Credenciales Gmail en secret manager / env cifrados.
- Los archivos de facturas contienen datos sensibles → cifrado en reposo si es posible.
- Dashboard protegido por autenticación.
- Rate limiting en Gmail API (respetar quotas).
- Backup diario de PostgreSQL + storage de archivos.
- Idempotencia: un mismo `gmail_id` nunca se procesa dos veces.

---

## 12. Puntos abiertos (resolver antes de codificar)

- Schema exacto del archivo X más frecuente (Facturae 3.2.x, UBL, otro).
- Volumen medio diario/mensual de correos con adjuntos.
- ¿Se permite uso de LLM local (Ollama) para casos ambiguos o solo reglas deterministas?
- Política de retención de correos originales y de archivos.
- ¿Dominio propio para el dashboard o subdominio interno?

---

## 13. Definición de Done por fase

Una fase se considera terminada cuando:

- Pasa tests de integración con al menos 5 ejemplos reales de cada tipo de correo.
- Logs permiten reconstruir exactamente qué se hizo con cada `gmail_id`.
- El dashboard refleja correctamente el estado.
- Se puede reprocesar un correo fallido desde la UI sin intervención manual en Gmail.
```

Tambien revisa el proyecto, la arquitectura, y asegurate que tiene todo bien descrito en un ARCHITECTURE.md, que cada tarea se describe en ISSUES.md y se trabaja y marca como hecha ahí asignando un Id por ejemplo TASK-XXXX, añade test unitarios y e2e con playwright y otro tipo de medidas como code linting etc, y asegurate que en el AGENTS.md todo este workflow está bien definido con reglas con nombres como RULE-001 y subsiguientes