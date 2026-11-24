# Feature Specification: PostgreSQL Container Runtime

**Feature Branch**: `004-postgres-container-runtime`

**Created**: 2026-11-24

**Status**: Draft

**Input**: User description: "Operate IncidentOps with a real database connectivity health check, transparent SQLite/PostgreSQL selection, temporal and functional parity between engines, and reproducible API/PostgreSQL container orchestration."

## Clarifications

### Session 2026-11-24

- Q: ¿Qué debe emitir el CLI cuando falla el chequeo de salud? → A: Escribir el JSON de error por stdout y terminar con código 1, tanto si `check_health()` retorna `False` como si lanza una excepción.
- Q: ¿Qué debe incluir la inicialización idempotente de PostgreSQL? → A: Crear tablas, índices y semillas de políticas SLA sin duplicarlos en inicializaciones repetidas, usando `CREATE TABLE IF NOT EXISTS` y `ON CONFLICT DO NOTHING`.
- Q: ¿Qué esquemas PostgreSQL debe aceptar `DATABASE_URL`? → A: Aceptar `postgresql://` y `postgres://`; aceptar `sqlite:///` para SQLite y rechazar otros esquemas con un error explícito.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consultar la salud real del servicio (Priority: P1)

Como operador, quiero comprobar la disponibilidad del servicio y su base de datos
por HTTP o CLI para distinguir una instancia lista de una degradada.

**Why this priority**: El runtime y los operadores necesitan conocer la
conectividad efectiva con la persistencia, no solo que el proceso de API está vivo.

**Independent Test**: Con un repositorio que responda y otro que falle, verificar
los cuerpos, códigos HTTP y resultados CLI definidos para ambos estados.

**Acceptance Scenarios**:

1. **Scenario: La base conectada informa salud correcta por HTTP y CLI**
   **Given** que la base de datos configurada acepta una consulta de conectividad,
   **When** el operador consulta la salud mediante HTTP o el comando CLI `health`,
   **Then** HTTP responde `200 OK` y CLI termina con código `0`,
   **And** ambas interfaces devuelven `{"status":"ok","database":"connected"}` tras
   una consulta real `SELECT 1` ejecutada por la persistencia.
2. **Scenario: La base inaccesible informa degradación controlada**
   **Given** que la verificación de conectividad falla o no puede completarse,
   **When** el operador consulta la salud por HTTP o CLI,
   **Then** HTTP responde `503 Service Unavailable` y CLI escribe por stdout
   `{"status":"error","database":"unavailable"}` y termina con código `1`,
   **And** el resultado es el mismo cuando la verificación devuelve `False` o
   lanza una excepción.

---

### User Story 2 - Seleccionar persistencia sin cambiar el uso del servicio (Priority: P1)

Como responsable de desarrollo u operaciones, quiero seleccionar SQLite o
PostgreSQL mediante configuración para usar el mismo servicio y los mismos casos
de uso en desarrollo, pruebas y producción.

**Why this priority**: La selección de motor habilita producción sobre PostgreSQL
sin perder la rapidez de SQLite local ni duplicar la lógica de negocio.

**Independent Test**: Construir el repositorio con cada forma de configuración y
verificar el motor seleccionado y el cumplimiento del mismo contrato de
persistencia.

**Acceptance Scenarios**:

3. **Scenario: La configuración elige el motor sin cambiar las interfaces**
   **Given** que `DATABASE_URL` contiene una URL `postgresql://...`,
   `postgres://...`, `sqlite:///...` o está ausente,
   **When** se construye el repositorio de la aplicación,
   **Then** ambas formas de URL PostgreSQL seleccionan PostgreSQL y la URL SQLite
   selecciona SQLite,
   **And** la ausencia de configuración selecciona SQLite en memoria
   (`sqlite:///:memory:`),
   **And** cualquier otro esquema se rechaza con un error explícito,
   **And** API, CLI y casos de uso conservan el mismo contrato de persistencia.

---

### User Story 3 - Operar el runtime en contenedores reproducibles (Priority: P1)

Como operador de producción, quiero iniciar el servicio y su base relacional
dedicada como una unidad reproducible para asegurar que la API arranque cuando la
base esté lista y que los datos persistan entre reinicios.

**Why this priority**: Una topología declarativa reduce diferencias de entorno y
evita iniciar la API antes de que la persistencia acepte conexiones.

**Independent Test**: Construir e iniciar la topología definida, verificar estado
saludable de los servicios, conectividad de API a PostgreSQL y persistencia de
datos al recrear el servicio de API.

**Acceptance Scenarios**:

4. **Scenario: La topología levanta API y base con dependencias saludables**
   **Given** que el runtime de contenedores está disponible y se inicia la
   topología de producción,
   **When** la base de datos supera su chequeo de disponibilidad,
   **Then** la API inicia después de que la base se declare saludable,
   **And** la base utiliza almacenamiento persistente y la API informa salud
   conectada mediante `/health`.

### Edge Cases

- Si el chequeo de conectividad retorna `False` o produce una excepción, el
  resultado externo debe ser el mismo estado degradado; no se deben exponer
  detalles internos ni credenciales.
- Una URL `DATABASE_URL` no soportada debe producir un error de configuración
  claro durante la construcción del repositorio, no cambiar silenciosamente de
  motor.
- Si PostgreSQL todavía no está disponible, la orquestación debe mantener la API
  sin iniciar hasta que el chequeo de salud de la base tenga éxito.
- La reinicialización repetida de cualquiera de los motores no debe borrar ni
  duplicar objetos del esquema.
- Los instantes equivalentes con diferentes offsets deben conservar orden y
  resultado de SLA idénticos después de normalizarse a UTC.

## Requirements *(mandatory)*

### Functional Requirements

- **RF-01 — Chequeo real de salud (API y CLI)**: El sistema MUST exponer `GET
  /health` y el subcomando CLI `health`. Ambos MUST consultar conectividad real
  mediante el contrato de persistencia, que ejecuta una consulta efectiva
  `SELECT 1`. Cuando la base responde, HTTP MUST retornar `200 OK`, CLI MUST
  terminar con código `0`, y ambas interfaces MUST devolver
  `{"status":"ok","database":"connected"}`.
- **RF-02 — Degradación controlada ante fallo de base de datos**: Si la
  verificación falla, retorna `False` o lanza una excepción, HTTP MUST retornar
  `503 Service Unavailable`; CLI MUST escribir por stdout
  `{"status":"error","database":"unavailable"}` y terminar con código `1`. Ambas
  interfaces MUST usar ese mismo resultado sin revelar detalles internos de
  conexión.
- **RF-03 — Selección transparente de motor por `DATABASE_URL`**: El sistema MUST
  seleccionar PostgreSQL para URLs con prefijo `postgresql://` o `postgres://`,
  SQLite para `sqlite:///` y SQLite en memoria (`sqlite:///:memory:`) cuando la
  variable esté ausente. Cualquier esquema no soportado MUST producir un error
  explícito en la fábrica de repositorios. La selección MUST ocurrir en la
  frontera de composición, detrás del mismo contrato de repositorio, sin cambios
  en reglas de dominio, casos de uso o adaptadores primarios.
- **RF-04 — Contrato compartido de persistencia**: Los adaptadores SQLite y
  PostgreSQL MUST implementar el mismo contrato de repositorio, incluyendo el
  chequeo real de conectividad, y MUST soportar las operaciones del ciclo de
  incidentes y evaluación SLA.

### Non-Functional Requirements — Operación y despliegue

- **RNF-01 — Paridad funcional y temporal entre motores**: SQLite y PostgreSQL
  MUST producir el mismo resultado funcional para operaciones equivalentes de
  incidentes y SLA. Al inicializar cada adaptador, ambos MUST crear de forma
  idempotente las tablas `sla_policies` e `incidents`, los índices requeridos
  (incluido `idx_incidents_dup_key`) y los datos semilla de políticas SLA. La
  inicialización MUST usar creación condicional de tablas e inserción de semillas
  que no duplique registros (`CREATE TABLE IF NOT EXISTS` y `ON CONFLICT DO
  NOTHING`, o una operación equivalente del motor). Ambos MUST almacenar marcas
  temporales como texto ISO 8601 normalizado a UTC.
- **RNF-02 — Empaquetado reproducible**: El servicio MUST poder construirse desde
  un `Dockerfile` basado en `python:3.12-slim` que use `uv` para instalar las
  dependencias bloqueadas del proyecto de forma reproducible. `.dockerignore`
  MUST excluir artefactos locales, caches, entornos virtuales y pruebas que no
  sean necesarias dentro de la imagen de producción.
- **RNF-03 — Orquestación reproducible y persistente**: `docker-compose.yml`
  MUST definir dos servicios: `db`, basado en `postgres:16-alpine`, y `api`.
  `db` MUST tener un volumen persistente y un healthcheck con `pg_isready`.
  `api` MUST recibir una `DATABASE_URL` que apunte al servicio `db`, depender de
  `db` con condición `service_healthy` y tener un healthcheck HTTP sobre
  `/health`.
- **RNF-04 — Límites de dependencias y proveedor**: El driver PostgreSQL
  `psycopg[binary]` MUST limitarse al adaptador outbound. El sistema MUST usar
  SQL explícito y MUST NOT introducir SQLAlchemy, SQLModel u otro ORM. Dominio,
  aplicación e inbound MUST NOT importar drivers de base de datos.

### Key Entities

- **Repository health**: Estado observable de conectividad del motor configurado,
  representado como disponible o no disponible sin exponer credenciales ni
  detalles internos.
- **Database configuration**: URL que determina el adaptador seleccionado en
  desarrollo/pruebas o producción.
- **Container runtime**: Topología de API y base de datos con dependencias de
  disponibilidad y persistencia de datos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: En todas las verificaciones con conectividad disponible, HTTP
  devuelve 200 y CLI código 0 con el mismo resultado JSON de salud.
- **SC-002**: En todas las verificaciones con conexión fallida o excepción, HTTP
  devuelve 503 y CLI código 1 con el mismo resultado JSON de degradación.
- **SC-003**: Las dos formas de URL PostgreSQL, la URL SQLite y la variable
  ausente seleccionan consistentemente el motor esperado; cualquier otro esquema
  genera un error explícito.
- **SC-004**: Todas las operaciones de aceptación de incidentes y SLA producen
  resultados equivalentes sobre SQLite y PostgreSQL para los mismos datos e
  instantes de referencia.
- **SC-005**: La topología contiene exactamente los servicios API y base de
  datos, y la API solo se considera saludable cuando el endpoint `/health`
  confirma conectividad.

## Assumptions

- ADR-004 gobierna la decisión de persistencia dual y es la autoridad para
  mantener el núcleo hexagonal y el SQL explícito sin ORM.
- PostgreSQL se reserva para despliegues contenedorizados/producción; SQLite en
  memoria es el default de desarrollo y pruebas rápidas.
- Las excepciones del puerto `check_health()` se convierten a un resultado
  degradado estable en las interfaces, sin incluir información sensible en la
  respuesta.
- Las credenciales de PostgreSQL se suministran mediante configuración de
  entorno y no se incorporan a la imagen del contenedor ni al repositorio.
- El volumen persistente de PostgreSQL se conserva al recrear el servicio API;
  el ciclo de vida/backups del volumen queda sujeto a la operación del entorno.
