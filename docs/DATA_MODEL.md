# Modelo de Datos – CRM Transporte

Este documento describe las entidades principales. Se irá ampliando conforme
avancemos en las fases (ver [ROADMAP.md](ROADMAP.md)).

CRM de uso interno (una sola empresa) — no hay tabla `Organization`/tenant.

Marcado ✅ lo ya implementado en `apps/api/src/models/` (migración verificada
contra SQLite y, desde TASK-0009, contra Postgres real) y ⏳ lo que falta
por construir (cliente Gmail real y extracción real de PDF).

---

## Identidad y acceso (Fase 1) ✅

### User

Login único tanto para padres como para el equipo interno.

- id
- email (único)
- passwordHash
- name
- role (`parent` | `staff` | `admin`)
- familyId (FK → Family, solo si `role = parent`)
- createdAt
- updatedAt

> **Invariante (RULE-005 de AGENTS.md):** toda consulta de datos de negocio
> hecha por un `User` con `role = parent` filtra obligatoriamente por su
> `familyId`. Ningún endpoint de negocio sin guard que lo aplique.

---

## Familias y alumnos (Fase 1) ✅

### Family

- id
- name
- address
- status (`active` | `inactive`)
- createdAt
- updatedAt

El listado staff (`GET /families`, TASK-0075) añade campos calculados que no
son columnas: `outstandingAmount`, `overdueAmount`, `unbilled`.

### Student (alumno)

- id
- familyId (FK → Family)
- name
- birthDate
- school (texto libre por ahora; entidad `School` propia si hiciera falta)
- status (`active` | `inactive`)
- createdAt
- updatedAt

### Contract (contrato de servicio)

Qué servicio de transporte tiene contratado un alumno. Sin `routeId` todavía
— se añade cuando entre la fase de rutas/vehículos, sin romper este modelo.

- id
- studentId (FK → Student)
- serviceType
- monthlyFee
- startDate
- endDate (nullable)
- status (`active` | `paused` | `cancelled`)
- createdAt
- updatedAt

---

## Proveedores (Fase 1/2) ✅

Alta y edición por staff (`POST/PATCH /suppliers`, TASK-0052). El `email` alimenta la clasificación del buzón.

### Supplier

- id
- name
- taxId
- email (nullable) — usado por la clasificación automática para distinguir
  factura de proveedor vs. factura a familia (TASK-0029)
- category (`fuel` | `maintenance` | `insurance` | `other`)
- createdAt
- updatedAt

---

## Ingesta de correo (Fase 2 — igual que el spec original en [SPEC_ORIGINAL.md](SPEC_ORIGINAL.md))

Esquema ✅ implementado; el pipeline simulado (FakeGmailClient) clasifica y
extrae. Gmail OAuth y extracción real de PDF siguen bloqueados (TASK-0032/0031).

### Email

- id
- gmailId (único)
- threadId
- subject
- fromAddress
- receivedAt
- rawHeaders (JSON)
- bodyPlain
- bodyHtml
- labels (array de texto)
- processingStatus (`pending` | `processing` | `processed` | `failed` | `ignored`)
- errorMessage
- createdAt
- updatedAt

### Document

- id
- emailId (FK → Email)
- documentType (`family_invoice` | `supplier_invoice` | `credit_note` | `other` | `unknown`)
- filePath
- originalFilename
- mimeType
- fileHash (SHA-256, para deduplicación)
- isZipMember
- parentZipId (nullable, FK → Document)
- createdAt

Descarga: `GET /documents/{id}/file` (TASK-0051). Staff cualquier adjunto; el padre solo el de una `FamilyInvoice` suya que no esté en `pending_review`.

---

## Facturación (Fase 2/3) — modelo ✅, sin datos reales todavía

Dos entidades separadas en vez de una `Invoice` polimórfica: la factura a
familia la ve el padre en el dashboard: la de proveedor es solo interna, con
otro ciclo de vida y otros campos.

### FamilyInvoice

- id
- documentId (FK → Document)
- familyId (FK → Family, **nullable**: la ingesta automática no sabe a qué
  familia pertenece un documento; nace sin enlazar y en `pending_review`
  hasta que staff lo asigna — TASK-0028/TASK-0030)
- studentId (FK → Student, nullable)
- contractId (FK → Contract, nullable)
- amount (se rellena al ingerir desde `extracted_data.total_amount`, parseo ES — TASK-0043)
- currency
- issueDate (igual, desde `extracted_data.issue_date`)
- dueDate (si staff publica sin fecha, se rellena a issueDate+30 días — TASK-0053)
- status (`pending_review` | `sent` | `paid` | `overdue`) — no se puede salir de `pending_review` sin `familyId`. El padre puede avisar «he pagado» (`POST /family-invoices/{id}/claim-payment`, TASK-0068): crea una `Task` de staff y **no** cambia el estado. Staff confirma con `POST /family-invoices/{id}/confirm-payment` (TASK-0071) o al pasar a `paid`; eso cierra la tarea. El padre no recibe `extractedData` (TASK-0074).
- paidAt (fecha en que quedó saldada, la del **último** cobro que la cubre — TASK-0102; nullable)
- paidAmount (calculado, no es columna: suma de sus `Payment`. La deuda de una factura es `amount - paidAmount` — TASK-0157)
- extractedData (JSON; copia cruda de la extracción, no es lo que ve el padre)
- confidence (float)
- createdAt
- updatedAt

### Payment (TASK-0157) ✅

Un cobro real sobre una `FamilyInvoice`. Antes `paid` era solo un valor de
`status`: sin fecha de cobro, sin importe, sin método y sin pagos parciales.

- id
- invoiceId (FK → FamilyInvoice)
- amount (> 0; nunca supera lo que queda pendiente)
- currency (la de la factura)
- paidOn (fecha en que **entró el dinero**; es la que cuenta para el cierre del mes, no `createdAt`)
- method (`transfer` | `direct_debit` | `card` | `cash` | `other`)
- reference (nullable)
- note (nullable)
- recordedBy (FK → User, nullable)
- createdAt

Reglas: un pago parcial deja la factura viva y su deuda baja al resto;
cuando los pagos cubren el importe pasa a `paid` con `paidAt` = fecha del
último pago, y queda en el audit trail. Marcar `paid` a mano (PATCH, `/bulk`,
`/confirm-payment`) registra un `Payment` por lo que faltase, con método
`other`. «Cobrado en el mes» suma `Payment.paidOn` dentro del mes (TASK-0102).

### SupplierInvoice

- id
- documentId (FK → Document)
- supplierId (FK → Supplier, nullable)
- category
- amount (también se rellena al ingerir, TASK-0043)
- currency
- issueDate
- dueDate
- status (`pending_review` | `approved` | `paid`)
- extractedData (JSON)
- confidence (float)
- createdAt
- updatedAt

### AuditLog ✅

Trazabilidad de cambios manuales — no solo facturas (TASK-0026): también
correcciones de `Family`/`Student`/`Contract`. `entityId` no es FK: según
`entityType` apunta a una tabla distinta.

- id
- entityType (`family` | `student` | `contract` | `family_invoice` | `supplier_invoice`)
- entityId
- fieldName
- oldValue
- newValue
- editedBy (FK → User)
- editedAt

---

## Notas y tareas de staff (hallazgo de auditoría comparativa 2026-08-25) ✅

Ninguna de las dos la ve nunca un `parent` — son herramientas de trabajo
interno del equipo, no un canal de comunicación con la familia. El aviso
«he pagado» del padre (TASK-0068) sí _crea_ una `Task` (`title` fijo
«El padre indica que ha pagado», `description` empieza por `invoice:{id}`);
el padre no lista ni lee esa tarea.

### Note (TASK-0025)

- id
- entityType (`family` | `student`)
- entityId
- body (texto libre)
- createdBy (FK → User)
- createdAt

Sin `updatedAt`: una corrección es nota nueva + borrar la vieja, no una edición.

### Task (TASK-0027)

- id
- familyId (FK → Family)
- title
- description (opcional)
- dueDate (opcional)
- status (`pending` | `done` | `cancelled`)
- assignedTo (FK → User, opcional)
- createdBy (FK → User)
- createdAt
- updatedAt

---

## Rutas y flota (Fase 5+, fuera de alcance por ahora)

Se desglosará cuando toque esa fase — no se modela todavía (ver ROADMAP.md).

---

## Notas de diseño

1. **Siempre** filtrar por `familyId` en el backend para usuarios `parent`.
2. Los emails se guardan en minúsculas y se normalizan.
3. `extractedData` (JSON) da flexibilidad sin crear columnas nuevas constantemente.
4. Los estados deben estar bien definidos en el código (enums), no strings sueltos.
5. Toda corrección manual de `extractedData` o de campos de facturación pasa
   por `AuditLog`.

## `NotificationOutbox` (TASK-0104)

Bandeja de salida de los avisos a las familias. Existe para que el envio
no viva dentro de la peticion que publica la factura.

| Campo                          | Notas                                                                                                |
| ------------------------------ | ---------------------------------------------------------------------------------------------------- |
| `kind`                         | `new_invoice` / `overdue_reminder` / `due_soon_reminder`                                             |
| `dedupe_key`                   | **unico**. `new_invoice:{invoice}:{parent}` o `{tipo}:{familia}:{parent}:{dia}`                      |
| `recipient`, `subject`, `body` | El correo ya compuesto: se encola lo que se va a mandar, no una referencia que pueda cambiar despues |
| `status`                       | `pending` / `sent` / `failed`                                                                        |
| `attempts`, `last_error`       | Se reintenta hasta 5 veces; despues queda `failed` con el motivo                                     |
| `sent_at`                      | Cuando salio de verdad, no cuando se encolo                                                          |

Migracion `8c52906e9cf4`, verificada upgrade y downgrade contra Postgres real.
