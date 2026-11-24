# Feature Specification: Incident Lifecycle and SLA

**Feature Branch**: `003-incident-lifecycle-sla`

**Created**: 2026-11-24

**Status**: Draft

**Input**: User description: "Gestionar el registro de incidentes, la detección de equivalentes abiertos y la consulta de su SLA tanto por API HTTP como por CLI, para garantizar trazabilidad inmediata ante fallas, evitar trabajo duplicado en operaciones y prevenir incumplimientos de nivel de servicio."

## Clarifications

### Session 2026-11-24

- Q: ¿Cómo deben interpretarse los timestamps ISO 8601 que llegan sin zona horaria? → A: Interpretarlos como UTC; convertir a UTC los que incluyan zona.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Registrar incidentes al recibirlos (Priority: P1)

Como responsable de operaciones, quiero registrar un incidente entrante por la
interfaz HTTP o la terminal para que quede trazable de inmediato y se conserve la
clasificación completa.

**Why this priority**: El registro es la base para detectar equivalentes y vigilar
el SLA.

**Independent Test**: Registrar un incidente válido por HTTP y CLI; verificar que
ambos devuelven el identificador, los datos persistidos, la clasificación y el
resultado de duplicados.

**Acceptance Scenarios**:

1. **Scenario: Registro inicial sin duplicados**
   **Given** que no existe un incidente equivalente y se recibe un título y
   `raw_text` no vacíos,
   **When** el operador registra el incidente por HTTP,
   **Then** la solicitud responde `201 Created` y persiste un incidente con estado
   `OPEN`,
   **And** la respuesta incluye la clasificación completa, `is_duplicate=false`,
   `duplicate_of=[]`, y un identificador `INC-` seguido de ocho dígitos
   hexadecimales si no se proporcionó uno.
2. **Scenario: Registrar un duplicado abierto e ignorar equivalentes resueltos**
   **Given** que existen incidentes con la misma `duplicate_group_key` en estados
   `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED` y `RESOLVED`,
   **When** el operador registra el reporte equivalente con un nuevo identificador,
   **Then** la solicitud responde `201 Created` y persiste el nuevo incidente,
   **And** `is_duplicate=true` y `duplicate_of` contiene los identificadores de
   todos los incidentes coincidentes en estado abierto, excluyendo el propio
   incidente nuevo y los incidentes `RESOLVED`.
3. **Scenario: Auditar SLA P2 a través de un fin de semana**
   **Given** que un incidente P2 fue recibido el viernes 6 de noviembre de 2026 a
   las 17:00,
   **When** se consulta su SLA el lunes 9 de noviembre de 2026 a las 09:00,
   **Then** la evaluación devuelve `elapsed_minutes=120`,
   `allowed_minutes=480`, `remaining_minutes=360`, `is_breached=false` y
   `requires_escalation=false`.
4. **Scenario: Informar que el incidente SLA no existe**
   **Given** que no existe el identificador solicitado,
   **When** el operador consulta su SLA por HTTP,
   **Then** la respuesta es `404 Not Found` y no contiene datos SLA inventados.
5. **Scenario: Rechazar una referencia SLA anterior a la recepción**
   **Given** que existe el incidente y la referencia temporal es anterior a su
   `created_at`,
   **When** el operador consulta su SLA por HTTP,
   **Then** la respuesta es `422 Unprocessable Entity` y no presenta una evaluación
   SLA.
6. **Scenario: Operar el registro y la auditoría SLA de forma equivalente por CLI**
   **Given** que se registra un incidente y luego se consulta su SLA usando el
   mismo instante de referencia que en HTTP,
   **When** el operador ejecuta los comandos CLI `create` y `sla`,
   **Then** `create` emite JSON con la clasificación completa y los mismos campos
   de duplicado que HTTP,
   **And** `sla` emite datos de negocio equivalentes a la respuesta HTTP.

### Edge Cases

- `title` o `raw_text` vacío o compuesto solo por espacios: API responde
  `422 Unprocessable Entity`; CLI termina con código 1; no se crea el incidente.
- `incident_id` omitido: generar un identificador único con formato
  `INC-<HEX8>`. Si se proporciona, conservarlo, siempre que no esté ya en uso.
- `created_at` omitido: usar el instante actual UTC. Si se proporciona, aceptar
  ISO 8601; una marca sin zona se interpreta como UTC y una con zona se normaliza
  a UTC.
- `status` omitido: usar `OPEN`. Si se proporciona, debe pertenecer a los estados
  válidos del dominio.
- La detección de duplicados compara únicamente `duplicate_group_key`, considera
  `OPEN`, `IN_PROGRESS` y `ESCALATION_REQUIRED`, excluye `RESOLVED` y el propio
  `incident_id` recién registrado.
- Si hay varios duplicados abiertos, `duplicate_of` incluye todos sus
  identificadores; la existencia de duplicados nunca bloquea el nuevo registro.
- `reference_time` omitido: evaluar con un solo instante actual UTC. Si se
  proporciona sin zona, interpretarlo como UTC; si tiene zona, normalizarlo a UTC.
- `reference_time` anterior a `created_at`: rechazar la consulta SLA con
  `422 Unprocessable Entity`; CLI termina con código 1.
- Un identificador inexistente durante la auditoría SLA: API responde
  `404 Not Found`; CLI informa el error y termina con código distinto de cero.
- Un incidente exactamente en el límite SLA no está incumplido; el incumplimiento
  ocurre solo cuando los minutos consumidos exceden el límite.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: La API HTTP MUST permitir registrar incidentes mediante
  `POST /api/v1/incidents`; la CLI MUST ofrecer el comando `create`.
- **FR-002**: La creación MUST exigir `title` y `raw_text` como cadenas no vacías
  después de quitar espacios en blanco. La API MUST devolver
  `422 Unprocessable Entity` si falta cualquiera de los valores o solo contiene
  espacios; la CLI MUST salir con código 1. Ningún error de validación MUST crear
  un incidente.
- **FR-003**: La creación MAY recibir `incident_id`, `created_at` y `status`.
  Si `incident_id` se omite, el sistema MUST generar un identificador único de
  formato `INC-<HEX8>`. Si `created_at` se omite, MUST usar el instante actual
  UTC. Si `status` se omite, MUST usar `OPEN`; cualquier estado proporcionado
  MUST pertenecer al conjunto de estados válidos del dominio.
- **FR-004**: Una creación válida MUST persistir el incidente y devolver
  clasificación completa, `is_duplicate` booleano y `duplicate_of` como lista de
  identificadores. La API MUST responder `201 Created`; el comando CLI MUST emitir
  JSON equivalente.
- **FR-005**: La clasificación MUST derivar y persistir la `duplicate_group_key`
  usando las reglas deterministas existentes del dominio.
- **FR-006**: La búsqueda de duplicados MUST comparar únicamente
  `duplicate_group_key`, incluir coincidencias en `OPEN`, `IN_PROGRESS` y
  `ESCALATION_REQUIRED`, excluir `RESOLVED` y excluir el `incident_id` del
  incidente recién creado.
- **FR-007**: Encontrar uno o más duplicados MUST NOT bloquear la creación. El
  resultado MUST establecer `is_duplicate=true` y enumerar todos los identificadores
  coincidentes en `duplicate_of`; sin coincidencias, MUST devolver `false` y una
  lista vacía.
- **FR-008**: La API MUST permitir auditar SLA mediante
  `GET /api/v1/incidents/{incident_id}/sla`; la CLI MUST ofrecer el comando `sla`
  con el identificador del incidente. Ambas interfaces MUST exponer los mismos
  datos de negocio.
- **FR-009**: La auditoría SLA MUST incluir estado actual, componente, severidad,
  `elapsed_minutes`, `allowed_minutes`, `remaining_minutes`, estado de
  incumplimiento y `requires_escalation`. Cuando el SLA se haya excedido, el
  resultado MUST informar también los minutos excedidos.
- **FR-010**: `reference_time` MUST ser opcional y aceptar un timestamp ISO 8601.
  Si se omite, MUST usarse un único instante actual UTC. Las marcas sin zona
  horaria MUST interpretarse como UTC; las marcas con zona MUST normalizarse a UTC.
- **FR-011**: Si el incidente no existe, la API MUST responder `404 Not Found` y
  no presentar evaluación SLA; la CLI MUST informar el error y terminar con código
  distinto de cero.
- **FR-012**: Si `reference_time` es anterior a `created_at`, la API MUST
  responder `422 Unprocessable Entity` y no presentar evaluación SLA; la CLI MUST
  informar el error y terminar con código 1.
- **FR-013**: El cálculo de SLA MUST usar las reglas de severidad y escalamiento
  existentes en el dominio. El escalamiento comienza al alcanzar el 75% del
  umbral SLA; el incumplimiento ocurre solo después de exceder el umbral.
- **FR-014**: Para entradas equivalentes, las interfaces HTTP y CLI MUST devolver
  resultados equivalentes de registro, clasificación, duplicados y auditoría SLA,
  admitiendo diferencias de presentación propias de cada interfaz.

### Key Entities

- **Incident**: Un reporte identificado de forma única con título, texto original,
  componente, severidad, `duplicate_group_key`, hora de recepción y estado
  (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED` o `RESOLVED`).
- **Classification**: Resultado determinista que incluye severidad, componente,
  justificación, equipo recomendado, clave de agrupación de duplicados y
  consistencia de la clasificación.
- **Duplicate result**: `is_duplicate` indica si hay coincidencias activas;
  `duplicate_of` enumera sus identificadores, excluyendo el propio incidente y
  cualquier incidente resuelto.
- **SLA evaluation**: Estado del incidente evaluado a un instante de referencia,
  con minutos consumidos, límite permitido, minutos restantes o excedidos,
  incumplimiento y escalamiento requerido.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% de las creaciones válidas responden `201` por HTTP o JSON por
  CLI y persisten un incidente con su clasificación completa.
- **SC-002**: 100% de las entradas con `title` o `raw_text` vacíos o en blanco
  reciben el error definido por su interfaz y no crean incidentes.
- **SC-003**: En cada creación con equivalentes, `duplicate_of` contiene todos y
  solo los identificadores activos coincidentes; los resueltos y el propio
  incidente nunca aparecen.
- **SC-004**: Para un mismo incidente e instante de referencia, la auditoría SLA
  devuelve valores idénticos en HTTP y CLI y respeta la política de severidad.
- **SC-005**: 100% de las consultas con identificador desconocido devuelven el
  error de no encontrado, y 100% de las referencias anteriores a `created_at`
  devuelven error de validación sin evaluación SLA.

## Assumptions

- Los niveles de severidad y sus políticas permanecen bajo la autoridad del
  dominio: P0 permite 60 minutos y P1 240 minutos continuos; P2 permite 480
  minutos y P3 1440 minutos, contando lunes a viernes de 08:00 a 18:00. No se
  excluyen festivos. El escalamiento comienza al alcanzar el 75%; el
  incumplimiento ocurre solo al exceder el límite.
- La clasificación deriva componente, severidad, justificación, equipo
  recomendado y `duplicate_group_key` desde el `raw_text` mediante las reglas
  deterministas existentes; `title` es el título presentado y persistido.
- `created_at` y `reference_time` se interpretan como UTC cuando no incluyen zona
  horaria; valores con zona se normalizan a UTC.
- Los estados válidos son `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED` y
  `RESOLVED`. La creación usa `OPEN` por defecto; un estado explícito se conserva
  si es válido.
- El resultado duplicado es una advertencia no bloqueante; cada reporte entrante
  válido queda registrado aunque encuentre equivalentes.
- Cambios posteriores de estado, incluida la resolución del incidente, quedan
  fuera de esta funcionalidad.
- No se modifican políticas de autenticación/autorización existentes ni se
  especifican nuevas.
