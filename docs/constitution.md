# Constitución del proyecto IncidentOps

Esta constitución establece principios arquitectónicos y de calidad para los hitos H001–H004 del roadmap. Las reglas del dominio tienen una única fuente de verdad; las capas externas las invocan, no las replican.

## 1. Dominio determinista único

- Las reglas de clasificación, severidad, enrutamiento y duplicados pertenecen al dominio. Para una misma entrada y referencia, deben producir resultados deterministas.
- Severidades: **P0** para indisponibilidad global de servicio crítico o exposición activa de datos entre organizaciones; **P1** para degradación severa de infraestructura compartida con riesgo de caída; **P2** para degradación moderada o bloqueo individual; **P3** para solicitudes cosméticas o mantenimiento preventivo no productivo.
- SLA: **P0** y **P1** se contabilizan 24/7; **P2** y **P3**, de lunes a viernes entre 08:00 y 18:00. El escalamiento preventivo se activa al alcanzar el 75% del SLA y permanece activo tras un incumplimiento, incluso si el incidente se resolvió.
- Los equipos válidos son `Backend-Core`, `Platform-SRE`, `Data-DBA` y `Security-IAM`. Los estados válidos son `OPEN`, `IN_PROGRESS`, `ESCALATION_REQUIRED` y `RESOLVED`.
- La clave de duplicado identifica componente y categoría de síntoma. Adaptadores y casos de uso no deben redefinir ni duplicar las reglas del dominio.

## 2. Arquitectura Hexagonal

- Se adopta la arquitectura de puertos y adaptadores descrita en ADR-003: `src/domain/` contiene el núcleo de reglas y modelos; `src/application/`, los casos de uso compartidos y puertos secundarios definidos mediante `typing.Protocol`.
- `IncidentService` coordina los casos de uso. Los adaptadores primarios de `src/adapters/inbound/` exponen API REST y CLI; un futuro adaptador MCP debe reutilizar la aplicación, no duplicar lógica.
- `src/adapters/outbound/` contiene adaptadores secundarios intercambiables para persistencia y otros servicios. El dominio no depende de frameworks, interfaces ni motores de base de datos.

## 3. Gobernanza técnica y calidad

- Python **>=3.10** y dependencias gestionadas con `uv`.
- API REST con FastAPI y Pydantic v2; CLI con Typer.
- Persistencia SQLite3 de la biblioteca estándar, sin ORMs pesados. Cambiar el motor de base de datos requiere un ADR previo.
- Los comportamientos se especifican en formato BDD (`Given / When / Then`) y se verifican con pruebas de aceptación automatizadas en `pytest`.
