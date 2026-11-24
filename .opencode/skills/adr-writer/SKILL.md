---
name: adr-writer
description: Redacta y registra Architecture Decision Records (ADRs) inmutables en docs/adr/ evaluando alternativas arquitectónicas reales con sus trade-offs. Usar cuando se solicite tomar o documentar una decisión estructural, tecnológica o de topología antes de especificar o planificar una feature.
---

# ADR Writer

## Reglas obligatorias

1. **Plantilla única (`docs/adr/000-template.md`):**
   - Lee siempre `docs/adr/000-template.md` antes de redactar y respeta exactamente su estructura y metadatos (`Estado`, `Fecha`, `Autor(es)`, `Reemplaza a`, `Reemplazado por`).
   - **Prohibido** añadir secciones fuera de la plantilla, como `Componentes Afectados` con rutas de archivos frágiles o listas tácticas de comandos CLI/SQL.

2. **Una decisión estructural por archivo (Append-Only):**
   - Documenta exactamente **1 sola decisión arquitectónica** estructural y difícil de revertir por archivo (`docs/adr/NNN-titulo-en-kebab-case.md`).
   - Nunca sobrescribas el contenido histórico de ADRs previos aceptados; si un nuevo ADR sustituye total o parcialmente a uno anterior, indícalo en `Reemplaza a` del nuevo archivo y actualiza únicamente `Reemplazado por` en el ADR antiguo.

3. **Comparación honesta de alternativas:**
   - Evalúa al menos **2 opciones arquitectónicas reales y viables** para el contexto del sistema.
   - Documenta ventajas y desventajas auténticas de cada opción; **prohibido** incluir opciones de relleno (*strawmen*) diseñadas solo para ser descartadas.

4. **Diagramas Mermaid exclusivamente estructurales (opcional):**
   - Si incluyes un diagrama Mermaid, debe mostrar únicamente **capas hexagonales, límites de puertos/adaptadores o topología de contenedores/componentes**.
   - **Prohibido** representar flujos algorítmicos (`if/else`), diagramas de secuencia detallados o esquemas de tablas SQL.

5. **Separación estricta respecto a Spec-Kit (`spec.md` y `plan.md`):**
   - **Prohibido** duplicar criterios funcionales o escenarios BDD (`Given/When/Then`) propios de `spec.md`.
   - **Prohibido** incluir listas de archivos a modificar, definiciones de DTOs o desgloses de tareas propios de `plan.md` y `tasks.md`.
