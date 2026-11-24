# Bitácora de Desarrollo Guiado por Especificaciones — Semana 2 (`SDD_LOG.md`)

**Estudiante(s)**: `Jonathan David Moncaleano Angel`
**Fecha**: `2026-11-24`
**Modelos Utilizados en OpenCode (Plan/Razonamiento vs. Build/Implementación)**: `GPT 6 Luna Medium / GPT 6 Luna Low`

---

## 1. Elicitación con `/speckit.clarify` y Auditoría con `/speckit.analyze`

### 1.1 Feature `003-incident-lifecycle-sla`
- **Ambigüedades y casos borde detectados con `/speckit.clarify`**:
  - **Validación y creación:** se hizo explícito que `title` y `raw_text` son obligatorios y que no se aceptan valores vacíos o compuestos solo por espacios (`422` en HTTP y código `1` en CLI). También se concretaron los valores por defecto y la generación de `incident_id` (`INC-<HEX8>`).
  - **Duplicados:** la búsqueda se limita a coincidencias por `duplicate_group_key` en los estados que la aplicación considera abiertos (`OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED`). Un incidente `RESOLVED` no cuenta como duplicado activo y el registro en creación se excluye de su propia búsqueda.
  - **SLA y tiempo:** `reference_time` acepta una fecha ISO 8601; una referencia anterior a `created_at` produce `422` o salida CLI `1`, y un identificador inexistente produce `404`. Los timestamps sin zona se interpretan como UTC y los que sí tienen zona se normalizan a UTC. Esto permitió probar de forma determinista un SLA P2 que cruza el fin de semana sin alterar la política de horario hábil.
- **Hallazgos o validaciones de `/speckit.analyze` antes de implementar**:
  - La revisión encontró un riesgo concreto: la consulta SQLite estaba tomando la decisión de qué estados significan “abierto”. Se devolvió esa autoridad al servicio/dominio y se dejó al repositorio únicamente aplicar el conjunto de estados recibido. La distinción importa: SQL puede filtrar datos, pero no debe convertirse en una segunda fuente de reglas de negocio.
  - La auditoría también mejoró la trazabilidad de las tareas y sus pruebas: se completaron los campos de la evaluación SLA, se pidió paridad del caso P2 entre HTTP y CLI, se aclaró la conservación de `resolved_at` y se retiraron marcas `[P]` cuando varias tareas modificaban el mismo archivo de pruebas. Así, la revisión no se limitó a que cada requisito “apareciera” en algún documento; comprobó que existiera una forma concreta de validarlo.

### 1.2 Feature `004-postgres-container-runtime`
- **Ambigüedades y RNF aclarados antes de diseñar PostgreSQL/Compose**:
  - **Salud del servicio:** tanto HTTP como `cli health` deben reflejar conectividad real. Si falla el chequeo o devuelve `False`, el CLI escribe el JSON estable de indisponibilidad por stdout y termina con código `1`; HTTP responde `503`. Ninguna interfaz expone credenciales ni detalles internos de conexión.
  - **Selección y límites de persistencia:** `DATABASE_URL` acepta `postgresql://` y `postgres://` para PostgreSQL, y `sqlite:///` para SQLite; si falta, se usa SQLite en memoria. La factory es la única frontera que selecciona el motor. `psycopg` y `sqlite3` quedan en outbound; no se introduce ORM.
  - **Paridad y arranque:** las tablas, índices y semillas de SLA se inicializan de forma idempotente. Ambos motores guardan timestamps ISO 8601 normalizados a UTC como `TEXT`. La conexión PostgreSQL es lazy para poder construir y probar la factory sin un daemon activo; la operación de salud sí ejecuta una consulta real.
  - **Empaquetado y orquestación:** se precisó la imagen `python:3.12-slim`, instalación bloqueada con `uv`, el `.dockerignore` y una topología Compose de dos servicios: `db` con `postgres:16-alpine`, volumen y `pg_isready`; `api` espera `service_healthy`, apunta al host `db` y expone `/health`.
- **Auditoría de consistencia antes de implementar:** `/speckit.analyze` detectó que no bastaba con mencionar los drivers: había que prohibir explícitamente tanto `psycopg` como `sqlite3` en las capas domain, application e inbound. También pidió precisar las firmas del puerto, mantener `open_statuses` como decisión del servicio y serializar las tareas que editan el mismo archivo de pruebas. Las tareas se ajustaron para comprobar estos límites y para comparar los resultados SLA de ambos motores con el mismo incidente y `reference_time`.
- **Por qué se conserva una prueba PostgreSQL como `SKIPPED`:** `test_postgres_repository_schema_crud_duplicate_and_sla_parity` está condicionada a `INCIDENTOPS_TEST_POSTGRES_URL`. Si no se define, pytest la omite deliberadamente: el ciclo local rápido puede seguir probándose con SQLite y dobles, sin exigir que cada desarrollador levante PostgreSQL o Docker. La prueba real sigue en la suite y comprueba esquema, CRUD, duplicados, timestamps y paridad SLA cuando hay una instancia disponible. En PowerShell, configura `INCIDENTOPS_TEST_POSTGRES_URL` con una base PostgreSQL de pruebas (`$env:INCIDENTOPS_TEST_POSTGRES_URL = "postgresql://..."`) y ejecuta `uv run pytest -v tests/test_spec_004_runtime_health.py::test_postgres_repository_schema_crud_duplicate_and_sla_parity`. Conviene usar una base descartable o dedicada, ya que el caso inicializa el esquema y escribe registros.

---

## 2. Comparación Crítica: SDD Manual (Iteración 1) vs. GitHub Spec Kit (Iteración 2 y Retos)

| Dimensión Comparada | SDD Manual (Iteración 1: `001`) | GitHub Spec Kit (Iteración 2 y Retos: `002`–`004`) |
| :--- | :--- | :--- |
| **Separación *QUÉ* vs. *CÓMO* vs. *TAREAS*** | La iteración manual permitió avanzar con rapidez, pero exigió disciplina para no mezclar comportamiento esperado con decisiones técnicas y pendientes de implementación. | `spec.md`, `plan.md` y `tasks.md` hacen visible esa separación y facilitan la trazabilidad. Aun así, la herramienta no impide por sí sola que una especificación incluya detalles prematuros; eso requiere criterio durante la revisión. |
| **Gestión de ambigüedades (`/speckit.clarify`)** | Las dudas podían resolverse durante la redacción, a veces sin dejar claro qué decisión se había tomado ni por qué. | La etapa de aclaración convierte supuestos relevantes en respuestas y criterios comprobables antes de planificar. Es especialmente útil cuando una diferencia pequeña —por ejemplo, un estado permitido o un código de error— cambia la prueba o la arquitectura. |
| **Consistencia con la Constitución (`/speckit.analyze`)** | La revisión depende de recordar límites y recorrer manualmente requisitos, tareas y archivos. | La auditoría busca contradicciones y huecos de cobertura de forma sistemática. En el hito 004, señalar los bans incompletos de drivers y las tareas de prueba sin orden explícito evitó dar por válido un plan que sonaba completo, pero aún dejaba riesgos ejecutables. |
| **Riesgo de verbosidad / exceso de Markdown** | Es menos probable producir artefactos largos por defecto, aunque se pueden omitir supuestos y dependencias. | La estructura ayuda a no olvidar secciones, pero puede producir repetición. La solución no fue aceptar todo el texto generado: revisé si cada requisito tenía una prueba y si cada tarea aportaba una acción distinta. |

- **Análisis basado en el artículo de Birgitta Böckeler en Martin Fowler**:
  1. **Nivel de uso en IncidentOps:** el proceso se ubica principalmente en **Spec-anchored**: las especificaciones guían el trabajo y sirven para discutir cambios, pero el código, las pruebas y las reglas de arquitectura siguen siendo la evidencia operativa. Al iniciar un hito hay un componente **Spec-first**, porque se aclara y acuerda el comportamiento antes de implementarlo. No es **Spec-as-source**: los documentos no se tratan como una descripción ejecutable que sustituya la revisión del sistema construido.
  2. **Cómo se evitó aprobar texto verboso a ciegas:** el roadmap acotó el alcance por hitos; después, la revisión se concentró en decisiones que podían cambiar el diseño o una prueba —fronteras hexagonales, fallos de conectividad, semántica de estados, paridad entre motores y dependencias de tareas—. El criterio no fue que el documento pareciera exhaustivo, sino que cada punto importante tuviera una consecuencia verificable. Las corridas de pytest y Ruff cerraron el ciclo contrastando lo escrito con el comportamiento y las fronteras reales.

---

## 3. *Commands* vs. *Agent Skills*, Arquitectura Hexagonal, ADRs y Uso de *Reasoning*

- **Diferencia entre *Commands* (`/speckit.*`) y *Agent Skills* (`hexagonal-architecture`, `bdd-acceptance`, `adr-writer`)**:
  Los comandos `/speckit.*` son los pasos del proceso: especificar, aclarar, planificar, generar tareas, analizar e implementar. Las *Agent Skills* no son comandos equivalentes ni crean etapas; aportan prácticas especializadas cuando hacen falta. `bdd-acceptance` ayuda a expresar comportamientos observables, `hexagonal-architecture` guía las dependencias entre capas y `adr-writer` estructura la evaluación de alternativas y el registro de decisiones.
  
  En este proyecto el orden **ADR → Constitución → Hito** dio coherencia al cambio de persistencia. ADR-004 registró la decisión de SQLite/PostgreSQL sin ORM y el runtime en contenedores; la Constitución convirtió esos límites en reglas obligatorias; luego el Hito 004 especificó y planificó el trabajo bajo esas reglas. ADR-003 había establecido previamente la arquitectura hexagonal que el nuevo hito debía preservar.
- **Valor de la Arquitectura Hexagonal**:
  La separación entre `IncidentService`, `IncidentRepositoryPort` y los adaptadores hizo posible atender el mismo caso de uso desde HTTP y CLI, y sumar PostgreSQL sin trasladar reglas de duplicados o SLA a SQL. El beneficio es concreto: cada adaptador resuelve detalles de su tecnología, mientras la aplicación conserva la política. La arquitectura no elimina el costo de mantener dos motores; hace visible dónde está ese costo y permite probar la paridad sin acoplar el núcleo a uno de ellos.
- **Uso intencional de *Reasoning / Extended Thinking* en OpenCode**:
  El razonamiento extendido conviene cuando hay que comparar alternativas o seguir una decisión a través de varios artefactos y capas: aclarar semántica, evaluar trade-offs y auditar dependencias. Una vez acordados el contrato, las firmas y los criterios de aceptación, un modelo rápido suele bastar para cambios locales y repetibles. No es una regla rígida por etapa: si durante la implementación aparece una decisión arquitectónica nueva, vuelve a ser preferible detenerse y razonar antes de editar.

---
## 4. Evidencia de Verificación Determinista
- **Análisis estático de fronteras hexagonales (`uv run ruff check src/`)**:
```text
All checks passed!
```
- **Salida completa de `uv run pytest -v`**:
```text
tests/test_spec_001_triage.py::test_critical_payment_outage_is_triaged_over_http PASSED                                                 [  2%]
tests/test_spec_001_triage.py::test_individual_account_lockout_mentioning_today_is_not_p0 PASSED                                        [  4%]
tests/test_spec_001_triage.py::test_empty_or_whitespace_input_returns_422[payload0] PASSED                                              [  6%]
tests/test_spec_001_triage.py::test_empty_or_whitespace_input_returns_422[payload1] PASSED                                              [  8%]
tests/test_spec_001_triage.py::test_cli_json_matches_http_result PASSED                                                                 [ 10%]
tests/test_spec_001_triage.py::test_cli_rejects_invalid_input_and_exits_with_code_one[args0] PASSED                                     [ 13%]
tests/test_spec_001_triage.py::test_cli_rejects_invalid_input_and_exits_with_code_one[args1] PASSED                                     [ 15%]
tests/test_spec_002_summary.py::test_summary_http_includes_only_active_records_and_does_not_mutate_storage PASSED                       [ 17%]
tests/test_spec_002_summary.py::test_summary_http_filters_component_and_recomputes_totals PASSED                                        [ 19%]
tests/test_spec_002_summary.py::test_summary_http_returns_valid_empty_summary_for_no_matches PASSED                                     [ 21%]
tests/test_spec_002_summary.py::test_summary_http_requires_timezone_in_reference_time PASSED                                            [ 23%]
tests/test_spec_002_summary.py::test_sqlite_repository_implements_port_and_repository_operations PASSED                                 [ 26%]
tests/test_spec_002_summary.py::test_repository_reads_legacy_naive_timestamps_as_utc PASSED                                             [ 28%]
tests/test_spec_002_summary.py::test_repository_factory_defaults_to_in_memory_and_rejects_unknown_schemes PASSED                        [ 30%]
tests/test_spec_002_summary.py::test_repository_factory_opens_absolute_sqlite_path PASSED                                               [ 32%]
tests/test_spec_002_summary.py::test_cli_summary_matches_http_and_keeps_storage_read_only PASSED                                        [ 34%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_http_creates_initial_incident_without_duplicates PASSED                                  [ 36%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_http_rejects_blank_required_fields_without_persisting[payload0] PASSED                   [ 39%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_http_rejects_blank_required_fields_without_persisting[payload1] PASSED                   [ 41%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_http_rejects_blank_required_fields_without_persisting[payload2] PASSED                   [ 43%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_open_duplicates_include_all_active_states_and_ignore_resolved PASSED                     [ 45%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_p2_sla_weekend_is_deterministic_and_matches_cli PASSED                                   [ 47%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_sla_not_found_returns_404_and_cli_exit_one PASSED                                        [ 50%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_sla_reference_before_created_returns_422_and_cli_exit_one PASSED                         [ 52%]
tests/test_spec_003_lifecycle_sla.py::test_bdd_cli_create_matches_http_classification_and_duplicate_fields PASSED                       [ 54%]
tests/test_spec_003_lifecycle_sla.py::test_cli_create_rejects_blank_values_with_exit_one PASSED                                         [ 56%]
tests/test_spec_003_lifecycle_sla.py::test_domain_sla_normalizes_naive_and_aware_timestamps PASSED                                      [ 58%]
tests/test_spec_003_lifecycle_sla.py::test_sqlite_preserves_resolved_at_and_rejects_duplicate_ids PASSED                                [ 60%]
tests/test_spec_004_runtime_health.py::test_health_api_maps_repository_status[repository0-200-expected_body0] PASSED                    [ 63%]
tests/test_spec_004_runtime_health.py::test_health_api_maps_repository_status[repository1-503-expected_body1] PASSED                    [ 65%]
tests/test_spec_004_runtime_health.py::test_health_api_maps_repository_status[repository2-503-expected_body2] PASSED                    [ 67%]
tests/test_spec_004_runtime_health.py::test_health_api_maps_repository_status[None-503-expected_body3] PASSED                           [ 69%]
tests/test_spec_004_runtime_health.py::test_health_cli_maps_repository_status[repository0-0-{"status": "ok", "database": "connected"}] PASSED [ 71%]
tests/test_spec_004_runtime_health.py::test_health_cli_maps_repository_status[repository1-1-{"status": "error", "database": "unavailable"}] PASSED [ 73%]
tests/test_spec_004_runtime_health.py::test_health_cli_maps_repository_status[repository2-1-{"status": "error", "database": "unavailable"}] PASSED [ 76%]
tests/test_spec_004_runtime_health.py::test_health_cli_maps_repository_status[None-1-{"status": "error", "database": "unavailable"}] PASSED [ 78%]
tests/test_spec_004_runtime_health.py::test_incident_service_health_is_false_without_repository PASSED                                  [ 80%]
tests/test_spec_004_runtime_health.py::test_factory_selects_sqlite_for_url_and_default PASSED                                           [ 82%]
tests/test_spec_004_runtime_health.py::test_factory_selects_postgres_for_supported_schemes[postgresql://] PASSED                        [ 84%]
tests/test_spec_004_runtime_health.py::test_factory_selects_postgres_for_supported_schemes[postgres://] PASSED                          [ 86%]
tests/test_spec_004_runtime_health.py::test_factory_rejects_unsupported_scheme PASSED                                                   [ 89%]
tests/test_spec_004_runtime_health.py::test_both_repositories_satisfy_runtime_checkable_port_without_postgres PASSED                    [ 91%]
tests/test_spec_004_runtime_health.py::test_sqlite_duplicate_query_uses_exact_supplied_statuses PASSED                                  [ 93%]
tests/test_spec_004_runtime_health.py::test_postgres_health_executes_select_one_and_handles_driver_error PASSED                         [ 95%]
tests/test_spec_004_runtime_health.py::test_postgres_repository_schema_crud_duplicate_and_sla_parity SKIPPED (Set INCIDENTOPS_TEST_...) [ 97%]
tests/test_spec_004_runtime_health.py::test_container_runtime_files_define_required_image_and_orchestration PASSED                      [100%]

======================================================= 45 passed, 1 skipped in 0.77s ========================================================
```
**Interpretación del test omitido**:
  `test_postgres_repository_schema_crud_duplicate_and_sla_parity` se omite cuando no está definida `INCIDENTOPS_TEST_POSTGRES_URL`. Es una decisión deliberada para que la suite local rápida no dependa de un daemon PostgreSQL o Docker activo; no se elimina ni se reemplaza la prueba real de integración. Con una instancia PostgreSQL disponible, se ejecuta así:
```text
$env:INCIDENTOPS_TEST_POSTGRES_URL = "postgresql://<credenciales-y-host>/<base-de-pruebas>"
uv run pytest -v tests/test_spec_004_runtime_health.py::test_postgres_repository_schema_crud_duplicate_and_sla_parity
```
- **Evidencia de CLI Typer y containerización (`docker compose config` / `docker compose up --build`)**:

	- **Validación de configuración de contenedores (`docker compose config`)**:
	```text
	> docker compose config
	name: starter-project
	services:
	api:
		build:
		context: P:\Universidad\Maestria\2026_2\ISIA\tallere_1\starter-project
		dockerfile: Dockerfile
		depends_on:
		db:
			condition: service_healthy
			required: true
		environment:
		DATABASE_URL: postgresql://incidentops:incidentops-local@db:5432/incidentops
		healthcheck:
		test:
			- CMD
			- python
			- -c
			- import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)
		timeout: 5s
		interval: 10s
		retries: 5
		start_period: 10s
		networks:
		default: null
		ports:
		- mode: ingress
			target: 8000
			published: "8000"
			protocol: tcp
	db:
		environment:
		POSTGRES_DB: incidentops
		POSTGRES_PASSWORD: incidentops-local
		POSTGRES_USER: incidentops
		healthcheck:
		test:
			- CMD-SHELL
			- pg_isready -U "$$POSTGRES_USER" -d "$$POSTGRES_DB"
		timeout: 3s
		interval: 5s
		retries: 10
		start_period: 10s
		image: postgres:16-alpine
		networks:
		default: null
		- type: volume
			source: postgres_data
			target: /var/lib/postgresql/data
			volume: {}
	networks:
	default:
		name: starter-project_default
	volumes:
	postgres_data:
		name: starter-project_postgres_data
	```
	- **Intento de arranque de contenedores (`docker compose up -d --build`)**:
	```text
	> docker compose up -d --build
	[+] Building 3.2s (13/13) FINISHED                                                                                                                                                      docker:default
	=> [api internal] load build definition from Dockerfile                                                                                                                                          0.4s
	=> => transferring dockerfile: 405B                                                                                                                                                              0.0s
	=> [api internal] load .dockerignore                                                                                                                                                             0.3s
	=> => transferring context: 269B                                                                                                                                                                 0.2s
	=> [api internal] load metadata for ghcr.io/astral-sh/uv:0.13.8                                                                                                                                  1.5s
	=> [api internal] load metadata for docker.io/library/python:3.12-slim                                                                                                                           1.9s
	=> [api] FROM ghcr.io/astral-sh/uv:0.13.8@sha256:5cc1805e2426484abca4ad46ea783bab281fdb225fd82d8ce6d66a81254bac85                                                                                0.0s
	=> [api stage-0 1/6] FROM docker.io/library/python:3.12-slim@sha256:191083cdf6c7bda8c76158983163ead5d5cf7b77cf3033e805bb0f5296f51b4b                                                             0.0s
	=> [api internal] load build context                                                                                                                                                             0.2s
	=> => transferring context: 4.04kB                                                                                                                                                               0.2s
	=> CACHED [api stage-0 2/6] COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /uvx /bin/                                                                                                               0.0s
	=> CACHED [api stage-0 3/6] WORKDIR /app                                                                                                                                                         0.0s
	=> CACHED [api stage-0 4/6] COPY pyproject.toml uv.lock ./                                                                                                                                       0.0s
	=> CACHED [api stage-0 5/6] RUN uv sync --locked --no-dev                                                                                                                                        0.0s
	=> CACHED [api stage-0 6/6] COPY src ./src                                                                                                                                                       0.0s
	=> [api] exporting to image                                                                                                                                                                      0.2s
	=> => exporting layers                                                                                                                                                                           0.0s
	=> => writing image sha256:49c7fbcdd9c80a38816ee0236b50afbc4d7ca00dec3ca6377f1702c1fd30b82e                                                                                                      0.1s
	=> => naming to docker.io/library/starter-project-api                                                                                                                                            0.1s
	[+] Running 2/2
	✔ Container starter-project-db-1   Healthy                                                                                                                                                       0.0s 
	✔ Container starter-project-api-1  Started 
	```
