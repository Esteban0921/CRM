# Modelo de Datos – CRM Transporte

Este documento describe las entidades principales. Se irá ampliando conforme
avancemos en las fases (ver [ROADMAP.md](ROADMAP.md)).

CRM de uso interno (una sola empresa) — no hay tabla `Organization`/tenant.

Marcado ✅ lo ya implementado en `apps/api/src/models/` (con migración
verificada contra SQLite; Postgres real pendiente, TASK-0009) y ⏳ lo que
falta por construir (el propio pipeline de ingesta, no solo su esquema).

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

Esquema ✅ implementado; el pipeline que realmente lee Gmail, descarga
adjuntos y clasifica ⏳ está bloqueado por decisiones externas (credenciales
OAuth, cuenta de pruebas, schema del XML — sección 12 de SPEC_ORIGINAL.md).

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
- amount
- currency
- issueDate
- dueDate
- status (`pending_review` | `sent` | `paid` | `overdue`)
- extractedData (JSON)
- confidence (float)
- createdAt
- updatedAt

### SupplierInvoice

- id
- documentId (FK → Document)
- supplierId (FK → Supplier, nullable)
- category
- amount
- currency
- issueDate
- dueDate
- status (`pending_review` | `approved` | `paid`)
- extractedData (JSON)
- confidence (float)
- createdAt
- updatedAt

### AuditLog ✅

Trazabilidad de correcciones manuales sobre metadatos extraídos (no cubierto
por el spec original). `entityId` no es FK: según `entityType` apunta a
`family_invoices` o a `supplier_invoices`, tablas distintas.

- id
- entityType (`family_invoice` | `supplier_invoice`)
- entityId
- fieldName
- oldValue
- newValue
- editedBy (FK → User)
- editedAt

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
