# Bitácora de Ingeniería de Prompts y Contexto — Semana 1 (`CONTEXT_LOG.md`)

**Estudiante**: `Jonathan David Moncaleano Angel`  
**Fecha**: `2026-11-15`  
**Modelos / Asistentes Utilizados**: `GPT-6 Luna`

---

## 1. De Prompts Pobres a Técnicas Clásicas de *Prompt Engineering* (Reto 1: `src/triage_rules.py`)

### 1.1 Diagnóstico de un Prompt Pobre y Ambiguo
Analiza el siguiente prompt deficiente para el Reto 1:
> *"El archivo `triage_rules.py` funciona mal con algunos tickets del JSON. Agrégale el equipo recomendado y una clave para duplicados, y no pongas P0 cuando no sea urgente."*

Documenta al menos **3 modos de fallo o ambigüedades** de este prompt (p. ej., ausencia de contexto de dominio, restricciones negativas difusas, falta de enumeración de equipos válidos o ausencia de ejemplos canónicos):
1. `Existe ambigüedad de valores válidos, al incluir en el prompt “agrega el equipo recomendado” y “una clave para duplicados” no indican qué valores deben tomar esas propiedades, la IA debe inferir qué equipos existen, cómo se llaman y qué significa exactamente un ticket duplicado. Esto puede producir estructuras incompatibles con el JSON esperado.`
2. `Existe ausencia de contexto y motivación de dominio, no explica qué representa P0, qué significa un duplicado ni para qué se utilizarán recommended_team y la clave de duplicado, La IA no tiene suficiente información para comprender las reglas de negocio. Proporcionar el propósito y el contexto ayuda al modelo a tomar decisiones más alineadas con el objetivo.`
3. `Existe falta de ejemplos canónicos, no proporciona ningún ticket de ejemplo ni muestra cuál debería ser su resultado esperado, en tareas con patrones o reglas sutiles, los ejemplos permiten mostrar exactamente el comportamiento esperado y reducen interpretaciones diferentes.`

### 1.2 Uso de *Self-Consistency*, *Chain-of-Thought* y *Few-Shot Prompting*
- ¿Cómo utilizaste *Chain-of-Thought* (`<analysis>`) y *Self-Consistency* (múltiples consultas independientes) para definir las reglas de clasificación de los casos ambiguos (`INC-1002`, `INC-1007`, `INC-1009`) y la agrupación de duplicados (`INC-1001`/`INC-1006` e `INC-1003`/`INC-1008`)?

Se uso el siguiente prompt

```markdown
Actúa como analista de clasificación y triage de incidentes de software.

Voy a proporcionarte dos fuentes de información:
1. El bloque <lsp_context> obtenido del código actual, que contiene la definición de classify_incident_report y el modelo TriageResult.
2. Los 10 incidentes contenidos en data/sample_incidents.json.
Tu tarea es analizar los incidentes utilizando EXCLUSIVAMENTE la información proporcionada. No inventes reglas, campos, equipos, prioridades ni relaciones que no estén respaldadas por los datos.

CONTEXTO DEL CÓDIGO:
<lsp_context symbol="classify_incident_report">
  <!-- 1. Definiciones de Tipos y Políticas (LSP Hover / Type Definition) -->
# [LSP textDocument/hover type] src\models.py:12
class SLARule:
    """Define el acuerdo de nivel de servicio (SLA) para un nivel de severidad."""

    severity: SeverityLevel
    max_resolution_minutes: int
    operates_24x7: bool
    escalation_threshold_ratio: float = 0.75

# [LSP textDocument/hover type] src\models.py:22
class Incident:
    """Representa un incidente registrado en la plataforma IncidentOps."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None

# [LSP textDocument/hover type] src\models.py:35
class SLAEvaluation:
    """Resultado determinista de la evaluación de SLA de un incidente."""

    incident_id: str
    severity: SeverityLevel
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    is_breached: bool
    requires_escalation: bool

# [LSP textDocument/hover type] src\models.py:48
class TriageResult:
    """Resultado estructurado producido por el clasificador de triaje con IA."""

    incident_id: str
    severity: SeverityLevel
    component: str
    rationale: str
    consistency_ratio: float = 1.0

# [LSP textDocument/hover symbol] src\sla_calculator.py:17
SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}

  <!-- 2. Definición Exacta del Símbolo (LSP GoToDefinition) -->
# [LSP textDocument/definition] src\triage_rules.py:27
def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica un reporte de incidente aplicando reglas heurísticas iniciales.

    DEUDA TÉCNICA INTENCIONAL:
    - Evalúa palabras sueltas ("hoy", "urgente") antes de analizar el impacto real
      (caída global vs. cuenta individual vs. entorno de staging).
    - No normaliza componentes ni identifica el equipo de guardia correspondiente.
    """
    text_lower = raw_text.lower()

    # Bug de diseño: si un usuario dice "necesito acceder hoy" por su cuenta bloqueada,
    # se dispara como P0 antes de verificar si es una caída global o un caso individual.
    if "urgente" in text_lower or "hoy" in text_lower or "502" in text_lower:
        severity: SeverityLevel = "P0"
    elif "94%" in text_lower or "timeout" in text_lower:
        severity = "P1"
    elif "lenta" in text_lower or "segundos" in text_lower:
        severity = "P2"
    else:
        severity = "P3"

    if "pago" in text_lower or "cobro" in text_lower or "tarjeta" in text_lower:
        component = "payments-gateway"
    elif "cuenta" in text_lower or "ingresar" in text_lower:
        component = "auth-identity"
    elif "postgresql" in text_lower or "conexiones" in text_lower:
        component = "database-cluster"
    elif "certificado" in text_lower or "tls" in text_lower:
        component = "infra-certificates"
    elif "botón" in text_lower or "color" in text_lower:
        component = "frontend-ui"
    else:
        component = "reporting-api"

    return TriageResult(
        incident_id=incident_id,
        severity=severity,
        component=component,
        rationale=f"Clasificación heurística legacy asignada a {component} ({severity}).",
    )

  <!-- 3. Referencias de Invocación en el Proyecto (LSP FindReferences) -->
# [LSP textDocument/references] src\triage_rules.py:77
  L76:     for item in incidents:
  L77:         result = classify_incident_report(item["id"], item["raw_text"])
  L78:         snippet = item["raw_text"][:45] + "..." if len(item["raw_text"]) > 45 else item["raw_text"]
</lsp_context>

DATOS DE LOS INCIDENTES:
[
  {
    "id": "INC-1001",
    "reporter": "carlos.mendoza@clientes-corp.com",
    "created_at": "2026-11-05T08:15:00",
    "raw_text": "URGENTE: El gateway de pagos devuelve HTTP 502 Bad Gateway en todas las transacciones con tarjeta de crédito desde hace 12 minutos. Ningún comercio puede cobrar."
  },
  {
    "id": "INC-1002",
    "reporter": "ana.gomez@clientes-corp.com",
    "created_at": "2026-11-05T09:10:00",
    "raw_text": "He intentado ingresar a mi cuenta tres veces y ahora aparece bloqueada. Necesito acceder hoy mismo porque debo enviar el informe de cierre a la junta directiva."
  },
  {
    "id": "INC-1003",
    "reporter": "soporte-nivel1@incidentops.internal",
    "created_at": "2026-11-05T10:05:00",
    "raw_text": "El dashboard de reportes históricos tarda cerca de 4.5 segundos en cargar cuando un cliente tiene más de 10,000 órdenes registradas. No da error, pero la experiencia es muy lenta."
  },
  {
    "id": "INC-1004",
    "reporter": "luis.torres@logistica-express.co",
    "created_at": "2026-11-05T11:20:00",
    "raw_text": "Sería excelente si pudieran cambiar el color del botón de exportar CSV a verde oscuro porque el gris actual casi no resalta en mi monitor secundario."
  },
  {
    "id": "INC-1005",
    "reporter": "alertas-monitoreo@incidentops.internal",
    "created_at": "2026-11-05T11:45:00",
    "raw_text": "El nodo primario de PostgreSQL muestra un uso de conexiones del 94% y timeouts intermitentes en el pool de conexiones del servicio de facturación."
  },
  {
    "id": "INC-1006",
    "reporter": "maria.rodriguez@retail-latam.com",
    "created_at": "2026-11-05T13:00:00",
    "raw_text": "Otra vez cayó la pasarela de cobros con tarjeta, a nuestros clientes les sale error 502 al intentar pagar el carrito de compras."
  },
  {
    "id": "INC-1007",
    "reporter": "auditoria@seguridad-fin.com",
    "created_at": "2026-11-05T14:30:00",
    "raw_text": "Detectamos que al cambiar el parámetro company_id en la URL del reporte PDF se pueden visualizar facturas pertenecientes a otra organización."
  },
  {
    "id": "INC-1008",
    "reporter": "pedro.sanchez@ventas-norte.com",
    "created_at": "2026-11-05T15:10:00",
    "raw_text": "El listado de planes e historial tarda más de 3 segundos en responder cada vez que abrimos la pestaña de clientes corporativos con más de 10,000 registros."
  },
  {
    "id": "INC-1009",
    "reporter": "elena.vargas@contabilidad-global.com",
    "created_at": "2026-11-05T16:40:00",
    "raw_text": "La exportación mensual a Excel se queda pensando unos 20 segundos pero al final sí descarga el archivo completo. Hoy tenemos cierre contable y nos preocupa que falle más tarde."
  },
  {
    "id": "INC-1010",
    "reporter": "devops-ci@incidentops.internal",
    "created_at": "2026-11-05T17:25:00",
    "raw_text": "El certificado TLS del entorno de staging vencerá en 14 días. Requiere rotación programada antes del próximo sprint."
  }
]
\

OBJETIVO DEL ANÁLISIS:

Analiza específicamente estos grupos:
- INC-1001 / INC-1006
- INC-1002
- INC-1003 / INC-1008
- INC-1007
- INC-1009
Para cada incidente determina:
1. Alcance:
   - ¿A cuántos usuarios, servicios o componentes afecta?
   - ¿El impacto parece individual, limitado o amplio?
   - ¿Qué evidencia del incidente sustenta esta conclusión?
2. Riesgo:
   - ¿Cuál es el riesgo operativo o funcional?
   - ¿Qué consecuencias podrían producirse?
   - ¿Qué evidencia sustenta la evaluación?
3. Prioridad:
   - Determina la prioridad que razonablemente correspondería según las reglas y el contexto proporcionado.
   - Presta especial atención a los casos en los que podría confundirse una incidencia grave con una P0.
   - No asumas que "urgente" significa automáticamente P0.
4. Agrupación de duplicados:
   - Determina si los incidentes pertenecen al mismo problema raíz o representan incidentes independientes.
   - Para INC-1001 e INC-1006, analiza explícitamente si son duplicados.
   - Para INC-1003 e INC-1008, analiza explícitamente si son duplicados.
   - Para INC-1002, INC-1007 e INC-1009, determina si deben permanecer independientes.
   - Justifica cada decisión utilizando evidencias concretas de los incidentes.
IMPORTANTE:
No quiero una respuesta basada únicamente en intuición.
Primero identifica las evidencias relevantes de cada incidente, después aplica los criterios disponibles y finalmente presenta la conclusión.

Realiza el análisis de forma independiente para cada incidente y evita asumir que dos tickets son duplicados únicamente porque tienen síntomas similares.

FORMATO DE RESPUESTA:

Primero presenta una tabla:

Incidente/Alcance/Riesgo/Prioridad/Grupo duplicado

Después presenta una sección "Análisis de duplicados" donde expliques:
- INC-1001 vs INC-1006
- INC-1003 vs INC-1008
- INC-1002
- INC-1007
- INC-1009
Para cada comparación indica:
- evidencias a favor de que sean duplicados;
- evidencias en contra;
- conclusión;
- nivel de confianza: alto, medio o bajo.
Finalmente presenta una sección "Ambigüedades detectadas" indicando qué decisiones no pueden determinarse inequívocamente con la información proporcionada y qué regla o dato adicional sería necesario para resolverlas.

No modifiques el código y no propongas todavía una implementación. El objetivo en esta etapa es únicamente analizar los casos y determinar las reglas y decisiones esperadas.
```

##### Chain-of-Thought
Para aplicar Chain-of-Thought, se pidió a la IA que analizara los incidentes antes de asignarles una clasificación, teniendo en cuenta su alcance, el riesgo y las posibles relaciones entre tickets. La idea era evitar que el modelo se limitara a identificar palabras clave y asignara prioridades automáticamente sin considerar el contexto de cada situación.

Esta técnica fue especialmente útil para analizar los casos ambiguos:

INC-1002: permitió identificar que mencionar la palabra «hoy» no significa necesariamente que exista una emergencia, ya que el problema reportado afecta a una cuenta individual.

INC-1007: permitió reconocer que la exposición de facturas de otra organización representa un riesgo de seguridad importante, aunque las reglas actuales del código no contemplen explícitamente este tipo de situación.

INC-1009: ayudó a diferenciar la urgencia del cierre contable de la gravedad del problema, teniendo en cuenta que la exportación tarda aproximadamente 20 segundos, pero finalmente se completa.

También se utilizó para comparar los posibles duplicados. En el caso de INC-1001 e INC-1006 se encontraron coincidencias en la pasarela de pagos y el error HTTP 502. Por otro lado, INC-1003 e INC-1008 presentan problemas de rendimiento similares, pero afectan funcionalidades diferentes y no existe evidencia suficiente para afirmar que tengan la misma causa raíz.

En general, esta técnica permitió justificar mejor las decisiones, identificar las limitaciones de las reglas actuales y evitar clasificaciones basadas únicamente en palabras aisladas.

##### Self-Consistency
Para aplicar Self-Consistency, se realizaron dos consultas independientes con la misma información: una utilizando el modelo en modo rápido y otra utilizando el modo Thinking. Posteriormente, se compararon las respuestas para identificar en qué decisiones coincidían y en cuáles existían diferencias.

Los resultados mostraron varias coincidencias importantes. Ambos análisis cuestionaron que INC-1002 e INC-1009 debieran clasificarse como P0 únicamente por mencionar la palabra «hoy». También identificaron el riesgo de seguridad de INC-1007 y coincidieron en que INC-1003 e INC-1008 no podían considerarse duplicados confirmados solamente por presentar síntomas de lentitud.

Sin embargo, también hubo diferencias. Por ejemplo, el modelo rápido dejó la prioridad de INC-1002 como ambigua, mientras que Thinking propuso P2. Para INC-1007, el primero señaló que no había información suficiente para determinar la prioridad, mientras que el segundo propuso P1. Asimismo, ambos relacionaron INC-1001 e INC-1006, pero Thinking planteó que podrían ser dos ocurrencias diferentes del mismo problema de pagos.

Esta comparación permitió identificar qué conclusiones se mantenían entre las consultas y cuáles dependían de una interpretación particular del modelo. También ayudó a reconocer que no siempre existe una única respuesta cuando faltan criterios de clasificación o información adicional.

En conclusión, Self-Consistency permitió contrastar diferentes interpretaciones del mismo conjunto de incidentes y tener mayor confianza en las conclusiones que se repetían, sin asumir que la coincidencia entre respuestas garantizaba que fueran correctas.

---

- Copia el prompt mejorado que empleaste aplicando las técnicas clásicas (`<role>`, `<domain_rules>` con justificación del *porqué*, `<examples>` *Few-Shot* y `<task>`):

```xml
<role> Actúa como ingeniero de software especializado en Python, diseño de modelos de datos y clasificación de incidentes de software.

Tu objetivo es analizar y refactorizar la implementación existente para mejorar la clasificación de incidentes, la asignación de equipos responsables y la detección de duplicados.
</role>

<context> El proyecto contiene una implementación de clasificación de incidentes en src/triage_rules.py y un modelo de resultados en src/models.py.

A continuación se proporciona el contexto obtenido mediante el análisis del código:

<lsp_context>
<lsp_context symbol="classify_incident_report">
  <!-- 1. Definiciones de Tipos y Políticas (LSP Hover / Type Definition) -->
# [LSP textDocument/hover type] src\models.py:12
class SLARule:
    """Define el acuerdo de nivel de servicio (SLA) para un nivel de severidad."""

    severity: SeverityLevel
    max_resolution_minutes: int
    operates_24x7: bool
    escalation_threshold_ratio: float = 0.75

# [LSP textDocument/hover type] src\models.py:22
class Incident:
    """Representa un incidente registrado en la plataforma IncidentOps."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None

# [LSP textDocument/hover type] src\models.py:35
class SLAEvaluation:
    """Resultado determinista de la evaluación de SLA de un incidente."""

    incident_id: str
    severity: SeverityLevel
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    is_breached: bool
    requires_escalation: bool

# [LSP textDocument/hover type] src\models.py:48
class TriageResult:
    """Resultado estructurado producido por el clasificador de triaje con IA."""

    incident_id: str
    severity: SeverityLevel
    component: str
    rationale: str
    consistency_ratio: float = 1.0

# [LSP textDocument/hover symbol] src\sla_calculator.py:17
SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}

  <!-- 2. Definición Exacta del Símbolo (LSP GoToDefinition) -->
# [LSP textDocument/definition] src\triage_rules.py:27
def classify_incident_report(incident_id: str, raw_text: str) -> TriageResult:
    """Clasifica un reporte de incidente aplicando reglas heurísticas iniciales.

    DEUDA TÉCNICA INTENCIONAL:
    - Evalúa palabras sueltas ("hoy", "urgente") antes de analizar el impacto real
      (caída global vs. cuenta individual vs. entorno de staging).
    - No normaliza componentes ni identifica el equipo de guardia correspondiente.
    """
    text_lower = raw_text.lower()

    # Bug de diseño: si un usuario dice "necesito acceder hoy" por su cuenta bloqueada,
    # se dispara como P0 antes de verificar si es una caída global o un caso individual.
    if "urgente" in text_lower or "hoy" in text_lower or "502" in text_lower:
        severity: SeverityLevel = "P0"
    elif "94%" in text_lower or "timeout" in text_lower:
        severity = "P1"
    elif "lenta" in text_lower or "segundos" in text_lower:
        severity = "P2"
    else:
        severity = "P3"

    if "pago" in text_lower or "cobro" in text_lower or "tarjeta" in text_lower:
        component = "payments-gateway"
    elif "cuenta" in text_lower or "ingresar" in text_lower:
        component = "auth-identity"
    elif "postgresql" in text_lower or "conexiones" in text_lower:
        component = "database-cluster"
    elif "certificado" in text_lower or "tls" in text_lower:
        component = "infra-certificates"
    elif "botón" in text_lower or "color" in text_lower:
        component = "frontend-ui"
    else:
        component = "reporting-api"

    return TriageResult(
        incident_id=incident_id,
        severity=severity,
        component=component,
        rationale=f"Clasificación heurística legacy asignada a {component} ({severity}).",
    )

  <!-- 3. Referencias de Invocación en el Proyecto (LSP FindReferences) -->
# [LSP textDocument/references] src\triage_rules.py:77
  L76:     for item in incidents:
  L77:         result = classify_incident_report(item["id"], item["raw_text"])
  L78:         snippet = item["raw_text"][:45] + "..." if len(item["raw_text"]) > 45 else item["raw_text"]
</lsp_context>
</lsp_context>

Los incidentes que deben utilizarse para validar la implementación se encuentran en:

data/sample_incidents.json

El archivo contiene diez reportes de incidentes. Utiliza su contenido como fuente de evidencia para diseñar y validar las reglas.
</context>

<domain_rules>
1. Severidad:

Debemos clasificar reportes de incidentes en cuatro niveles de severidad:
-  P0 (SLA 60 min, guardia 24/7): Indisponibilidad global de un servicio crítico
(ej. pagos HTTP 502) o brecha activa de seguridad / fuga de datos entre
organizaciones (multi-tenant).
- P1 (SLA 240 min, guardia 24/7): Degradación severa de infraestructura compartida
con riesgo inminente de caída (ej. pool de conexiones de base de datos >90%).
- P2 (SLA 480 min, horario hábil L-V 08:00-18:00): Degradación moderada de
rendimiento sin caída del servicio (ej. reportes lentos >3s) o bloqueo operativo
que afecta únicamente a un usuario individual.
- P3 (SLA 1440 min, horario hábil): Solicitudes cosméticas de UI o tareas
preventivas de mantenimiento en entornos no productivos (staging).
La clasificación debe considerar el alcance, el impacto funcional y el riesgo. No asignes prioridades críticas únicamente por palabras como "hoy" o "urgente".

Justificación:
Es necesario diferenciar la urgencia expresada por quien reporta el incidente de su impacto real sobre el servicio y los usuarios.
2. Equipos:
Los cuatro equipos válidos para el campo recommended_team son:

Backend-Core , Platform-SRE , Data-DBA o Security-IAM

Selecciona exclusivamente uno de estos equipos según la funcionalidad afectada y la evidencia disponible.

Justificación:
Limitar los valores permitidos evita recomendaciones inconsistentes y garantiza que el resultado utilice los equipos reconocidos por el proyecto.
3. Duplicados:
Utiliza duplicate_group_key para identificar incidentes que correspondan al mismo problema.

duplicate_group_key : Una clave normalizada ( <component>:
<symptom_category> ) que permita detectar que INC-1001 e INC-1006
(ambos sobre error 502 en pagos) o INC-1003 e INC-1008 (ambos sobre lentitud
>3s con 10,000 registros) son incidentes duplicados del mismo problema subyacente.

Compara la funcionalidad afectada, los síntomas, los componentes y la evidencia disponible. No agrupes incidentes únicamente porque tengan palabras clave o síntomas similares.

Los incidentes independientes deben tener claves diferentes. Los incidentes que correspondan al mismo problema deben compartir una clave.

Justificación:
Una agrupación incorrecta puede distorsionar el seguimiento y el análisis de los incidentes.
4. Justificación:
Cada clasificación debe incluir una explicación basada en la información del reporte. Cuando no exista evidencia suficiente, reconoce la incertidumbre en lugar de inventar una causa o un impacto.
</domain_rules>

<examples>

<example name="Incidentes relacionados con pagos">

Incidente 1:
INC-1001: Los comercios no pueden realizar cobros con tarjeta y se presentan errores HTTP 502 en la pasarela de pagos.

Incidente 2:
INC-1006: Los clientes no pueden completar pagos con tarjeta y se reportan errores HTTP 502.

Resultado esperado:
- Reconocer que ambos reportes afectan la funcionalidad de pagos.
- Identificar las coincidencias en los síntomas.
- Evaluar si existe evidencia suficiente para considerarlos parte del mismo problema.
- Si se establece que son duplicados, asignarles el mismo duplicate_group_key.
- Justificar la decisión utilizando la información de los reportes.
No asumir que todos los errores HTTP 502 corresponden automáticamente a P0.
</example>

<example name="Incidentes de rendimiento">

Incidente 1:
INC-1003: El dashboard de reportes históricos tarda aproximadamente 4.5 segundos al consultar más de 10.000 órdenes.

Incidente 2:
INC-1008: El listado de clientes corporativos tarda más de 3 segundos al consultar más de 10.000 registros.

Resultado esperado:
- Reconocer que ambos presentan problemas de rendimiento.
- Diferenciar las funcionalidades afectadas.
- Evitar agruparlos únicamente por compartir síntomas de lentitud.
- Mantener claves diferentes mientras no exista evidencia suficiente de una causa común.
Justificar la decisión con base en los reportes.
</example>

</examples>

<task>

Refactoriza los siguientes archivos:
- src/models.py
- src/triage_rules.py
El objetivo es que el sistema clasifique correctamente los diez incidentes de data/sample_incidents.json.

Realiza los siguientes cambios:
1. Actualiza TriageResult en src/models.py para incorporar los campos:
   - recommended_team
   - duplicate_group_key
   Conserva los campos existentes que sigan siendo necesarios y utiliza tipos apropiados.
2. Refactoriza classify_incident_report en src/triage_rules.py para que:
   - Asigne una severidad según los criterios definidos.
   - Recomiende uno de los cuatro equipos válidos.
   - Identifique y agrupe los incidentes duplicados mediante duplicate_group_key.
   - Proporcione una justificación clara para cada clasificación.
3. Mantén la implementación consistente con la arquitectura y convenciones actuales del proyecto.
4. Evita introducir reglas, campos o dependencias que no sean necesarios.
5. No inventes información cuando los reportes sean ambiguos.
Antes de modificar el código, explica brevemente las limitaciones de la implementación actual y los cambios que propones.

Después, presenta el contenido completo de los dos archivos modificados, indicando claramente cuál corresponde a cada uno.

La implementación debe permitir ejecutar:

uv run python -m src.triage_rules

Finalmente, explica cómo verificar que los diez incidentes tengan una clasificación, un equipo recomendado y una clave de duplicados coherentes con la evidencia disponible.

</task>
```

---

## 2. Flujo Explorar $\rightarrow$ Destilar $\rightarrow$ Ejecutar en Contexto Limpio (Reto 2: Cálculo de SLA en Horario Hábil y ADR-002)

### 2.1 Exploración de Diseño (Sin Generar Código Aún) y Destilación
- **Objetivo explorado**: Diseño del algoritmo de cálculo de SLA en horario hábil (`P2`/`P3`, Lunes–Viernes 08:00–18:00) vs. 24/7 (`P0`/`P1`) y regla de escalamiento preventivo al 75%.
- **Síntesis de tu exploración de alternativas y resumen destilado (máx. 10 líneas)**:
Se exploraron tres alternativas: iteración día por día, cálculo matemático por semanas completas y uso de librerías externas. Se seleccionó la iteración diaria por su simplicidad, legibilidad y facilidad de pruebas.
Se identificaron casos borde como incidentes creados en fines de semana, antes de las 08:00, después de las 18:00 y aquellos que atraviesan varios fines de semana.
P0 y P1 contabilizarán todos los minutos transcurridos (24/7).
P2 y P3 contabilizarán únicamente minutos de lunes a viernes, entre las 08:00 y las 18:00 (máximo 600 minutos diarios).
Los intervalos se limitarán al horario laboral y los fines de semana contabilizarán cero minutos.
El cálculo recorrerá cada día del intervalo, manteniendo complejidad temporal O(D).
El escalamiento se activará al alcanzar el 75% del SLA y permanecerá activo después del incumplimiento.
Se descartó el cálculo por semanas completas por su mayor complejidad y las librerías externas por introducir dependencias innecesarias.
Se deben validar las zonas horarias, los límites temporales y el tratamiento de festivos entre semana.
También debe confirmarse el comportamiento del escalamiento para incidentes resueltos que incumplieron el SLA.

### 2.2 Ejecución con Contexto Curado en Nuevo Chat Limpio (*Context Engineering*)
Copia el prompt estructurado con etiquetas XML que utilizaste en un nuevo chat limpio para generar el **ADR (`docs/adr/002-calculo-sla-horario-habil.md`)** y la refactorización de `src/sla_calculator.py`:

```xml
<role>

Actúa como arquitecto de software senior con experiencia en Architecture Decision Records (ADR), Python, diseño de algoritmos y sistemas de gestión de incidentes.
</role>
<context>

Estoy trabajando en IncidentOps, una plataforma de gestión de incidentes que requiere corregir el cálculo de SLA en `src/sla_calculator.py`.

El siguiente bloque contiene el contexto técnico real de la función que se va a modificar:

<lsp_context symbol="evaluate_sla_status">
  <!-- 1. Definiciones de Tipos y Políticas (LSP Hover / Type Definition) -->
# [LSP textDocument/hover type] src\models.py:13
class SLARule:
    """Define el acuerdo de nivel de servicio (SLA) para un nivel de severidad."""

    severity: SeverityLevel
    max_resolution_minutes: int
    operates_24x7: bool
    escalation_threshold_ratio: float = 0.75

# [LSP textDocument/hover type] src\models.py:23
class Incident:
    """Representa un incidente registrado en la plataforma IncidentOps."""

    incident_id: str
    title: str
    component: str
    severity: SeverityLevel
    status: IncidentStatus
    created_at: datetime
    resolved_at: Optional[datetime] = None

# [LSP textDocument/hover type] src\models.py:36
class SLAEvaluation:
    """Resultado determinista de la evaluación de SLA de un incidente."""

    incident_id: str
    severity: SeverityLevel
    elapsed_minutes: int
    allowed_minutes: int
    remaining_minutes: int
    is_breached: bool
    requires_escalation: bool

# [LSP textDocument/hover type] src\models.py:49
class TriageResult:
    """Resultado estructurado producido por el clasificador de triaje con IA."""

    incident_id: str
    severity: SeverityLevel
    component: str
    rationale: str
    recommended_team: RecommendedTeam
    duplicate_group_key: str
    consistency_ratio: float = 1.0

# [LSP textDocument/hover symbol] src\sla_calculator.py:17
SLA_POLICY_TABLE: Dict[SeverityLevel, SLARule] = {
    "P0": SLARule(severity="P0", max_resolution_minutes=60, operates_24x7=True),
    "P1": SLARule(severity="P1", max_resolution_minutes=240, operates_24x7=True),
    "P2": SLARule(severity="P2", max_resolution_minutes=480, operates_24x7=False),
    "P3": SLARule(severity="P3", max_resolution_minutes=1440, operates_24x7=False),
}

  <!-- 2. Definición Exacta del Símbolo (LSP GoToDefinition) -->
# [LSP textDocument/definition] src\sla_calculator.py:25
def get_sla_rule_for_severity(severity: SeverityLevel) -> SLARule:
    """Obtiene la regla de SLA aplicable a una severidad validada contra latabla."""
    if severity not in SLA_POLICY_TABLE:
        raise ValueError(f"Severidad no válida: {severity}")
    return SLA_POLICY_TABLE[severity]

# [LSP textDocument/definition] src\sla_calculator.py:32
def evaluate_sla_status(incident: Incident, reference_time: datetime) -> SLAEvaluation:
    """Evalúa si un incidente ha incumplido su SLA o requiere escalamiento preventivo.

    Args:
        incident: Entidad del incidente a evaluar.
        reference_time: Marca de tiempo actual o de cierre contra la cual medir.

    Returns:
        SLAEvaluation con los minutos transcurridos, restantes y banderas de estado.
    """
    rule = get_sla_rule_for_severity(incident.severity)
    end_time = incident.resolved_at or reference_time

    if end_time < incident.created_at:
        raise ValueError("El tiempo de referencia no puede ser anterior a la creación.")

    # TODO(week-1-taller): Cuando rule.operates_24x7 es False (P2 y P3), solo deben
    # contabilizarse los minutos dentro del horario hábil (Lunes-Viernes 08:00-18:00).
    delta_seconds = (end_time - incident.created_at).total_seconds()
    elapsed_minutes = int(delta_seconds // 60)

    remaining_minutes = rule.max_resolution_minutes - elapsed_minutes
    is_breached = elapsed_minutes > rule.max_resolution_minutes

    escalation_limit = int(rule.max_resolution_minutes * rule.escalation_threshold_ratio)
    requires_escalation = (
        incident.status != "RESOLVED"
        and not is_breached
        and elapsed_minutes >= escalation_limit
    )

    return SLAEvaluation(
        incident_id=incident.incident_id,
        severity=incident.severity,
        elapsed_minutes=elapsed_minutes,
        allowed_minutes=rule.max_resolution_minutes,
        remaining_minutes=remaining_minutes,
        is_breached=is_breached,
        requires_escalation=requires_escalation,
    )

  <!-- 3. Referencias de Invocación en el Proyecto (LSP FindReferences) -->
# [LSP textDocument/references] src\incident_repository.py:146
  L145:             )
  L146:             sla_eval = evaluate_sla_status(incident, reference_time=reference_time)
  L147:             results.append(

# [LSP textDocument/references] src\sla_calculator.py:87
  L86:     monday_morning = datetime(2026, 11, 9, 9, 0, 0)
  L87:     evaluation = evaluate_sla_status(sample_incident, reference_time=monday_morning)
  L88: 
</lsp_context> <lsp_context>]
</context>

<adr_template>
El documento debe respetar la estructura y las convenciones establecidas en la plantilla oficial del proyecto.

<adr_template>
 docs/adr/000-template.md
</adr_template>
</adr_template>


<decision_summary>
1. Seleccionar iteración día por día mediante intersección de intervalos laborales, sin dependencias externas.
2. P0 y P1 contabilizan todos los minutos transcurridos (operación 24/7).
3. P2 y P3 contabilizan minutos de lunes a viernes, de 08:00 a 18:00, máximo 600 por jornada.
4. Las creaciones anteriores a las 08:00 comienzan a contabilizar desde esa hora; las posteriores a las 18:00, desde el siguiente día hábil.
5. Sábados y domingos contabilizan cero minutos para P2 y P3.
6. Recorrer los días del intervalo entre creación y evaluación, manteniendo complejidad temporal O(D).
7. Activar el escalamiento al alcanzar el 75% del SLA y mantenerlo activo después del incumplimiento.
8. Descartar el cálculo matemático por semanas completas por su mayor complejidad y las librerías externas por dependencias innecesarias.
9. Conservar el truncamiento de minutos y validar fechas y zonas horarias.
10. Confirmar el tratamiento de festivos entre semana y el escalamiento de incidentes resueltos que incumplieron el SLA.
</decision_summary>

<constraints>

1. P0 y P1 deben contabilizar tiempo de manera continua, las 24 horas del día y los 7 días de la semana.
2. P2 y P3 deben contabilizar únicamente tiempo hábil.
3. El horario hábil corresponde a lunes a viernes de 08:00 a 18:00.
4. Cada jornada laboral tiene un máximo de 600 minutos contabilizables.
5. Los sábados y domingos no contabilizan tiempo para P2 y P3.
6. Un incidente sin resolver debe activar el escalamiento cuando alcance o supere el 75% del tiempo permitido por su SLA.
7. Si el SLA ya fue incumplido (`is_breached=True`), `requires_escalation` debe permanecer activado.
8. La solución debe ser sencilla, legible, mantenible y sin dependencias externas pesadas.
9. La complejidad temporal esperada para el cálculo de horario hábil es O(D), donde D es el número de días del intervalo.
10. Se deben respetar los modelos, campos y estructuras existentes en el código. No se deben inventar atributos ni modificar contratos sin justificación.

</constraints>

<task>

Genera el documento:

`docs/adr/002-calculo-sla-horario-habil.md`

El ADR debe documentar formalmente la decisión arquitectónica para corregir el cálculo de SLA en horario hábil y el escalamiento preventivo.

El documento debe:

1. Seguir la estructura de la plantilla ADR proporcionada.
2. Describir el contexto y el problema técnico actual.
3. Explicar las reglas del dominio para incidentes 24/7 y horario hábil.
4. Documentar las alternativas evaluadas y la decisión seleccionada.
5. Justificar la complejidad temporal O(D).
6. Explicar cómo se manejan los casos borde de creación y evaluación fuera del horario laboral, fines de semana y múltiples semanas.
7. Documentar la lógica de escalamiento preventivo y la persistencia del escalamiento después de incumplir el SLA.
8. Identificar consecuencias positivas, negativas y posibles riesgos.
9. Incluir un diagrama Mermaid (`flowchart TD` o `stateDiagram-v2`) que represente el flujo de cálculo del tiempo y la transición al escalamiento.

El diagrama debe ser coherente con la decisión arquitectónica documentada.

</task>

```

---

## 3. Tipos de Modelos y Matriz de Decisión Arquitectónica

### 3.1 Comparación de Tipos de Modelos
Compara el comportamiento que observaste al interactuar con:
1. **Modelo Rápido / Estándar (ej. Flash, Mini, Haiku o modo estándar)**:
2. **Modelo de Razonamiento Extendido (*Thinking Model*)**:
- ¿En cuál de las tareas de la semana fue indispensable el modelo de razonamiento y en cuál bastó el modelo rápido?

### 3.2 Matriz de Decisión Arquitectónica
Para la plataforma *IncidentOps* y su evolución futura, justifica qué paradigma es el adecuado en cada escenario:

| Escenario / Requerimiento | Paradigma Elegido (Código Determinista / ML Clásico / Asistente GenAI en Chat / LLM en Tiempo de Ejecución) | Justificación Técnica (Determinismo, Costo, Latencia, Riesgo de Alucinación) |
| :--- | :--- | :--- |
| 1. Contabilizar minutos hábiles transcurridos y verificar si un ticket superó el 75% de su SLA | | |
| 2. Explorar casos borde y redactar un ADR antes de modificar la arquitectura de consultas SQL | | |
| 3. Detectar anomalías numéricas en millones de métricas de CPU/RAM por minuto | | |
| 4. Clasificar reportes de incidentes redactados en lenguaje natural abierto cuando las reglas deterministas no cubren nuevos patrones | | |

---

## 4. Economía de Tokens y Curaduría de Contexto con `tiktoken` (LSP vs. `grep`/`read` vs. `glob`/`read`)

### 4.1 Medición Empírica en *IncidentOps*
Completa la tabla con los resultados obtenidos al auditar los símbolos con `uv run python -m src.context_audit --symbol evaluate_sla_status` (y `classify_incident_report`):

#### uv run python -m src.context_audit --symbol classify_incident_report
====================================================================================
AUDITORÍA DE CONTEXT ENGINEERING: Símbolo objetivo `classify_incident_report`
 Tokenizador activo: tiktoken (o200k_base)
====================================================================================
Estrategia                             | Alcance            | Caracteres | Tokens
------------------------------------------------------------------------------------
1. Fuerza Bruta (glob + read todo)     | 9 archivos         | 45675      | 11325 tokens
2. Búsqueda Textual (grep + read .py)  | 2 archivos .py     | 8236       | 1972 tokens
3. Semántica vía LSP (AST/Symbols)     | Definición+Refs    | 7385       | 1809 tokens
------------------------------------------------------------------------------------
-> Reducción LSP vs. Fuerza Bruta (`glob` + `read`): 84.0% menos tokens
-> Reducción LSP vs. Búsqueda (`grep` + `read` .py): 8.3% menos tokens

#### uv run python -m src.context_audit --symbol evaluate_sla_status

====================================================================================
 AUDITORÍA DE CONTEXT ENGINEERING: Símbolo objetivo `evaluate_sla_status`
 Tokenizador activo: tiktoken (o200k_base)
====================================================================================
Estrategia                             | Alcance            | Caracteres | Tokens
------------------------------------------------------------------------------------
1. Fuerza Bruta (glob + read todo)     | 9 archivos         | 45675      | 11325 tokens
2. Búsqueda Textual (grep + read .py)  | 4 archivos .py     | 26676      | 6520 tokens
3. Semántica vía LSP (AST/Symbols)     | Definición+Refs    | 4383       | 1118 tokens
------------------------------------------------------------------------------------
-> Reducción LSP vs. Fuerza Bruta (`glob` + `read`): 90.1% menos tokens
-> Reducción LSP vs. Búsqueda (`grep` + `read` .py): 82.9% menos tokens


### 4.2 Comparación de Formatos de Serialización (`--compare-formats`)
Registra los tokens medidos con `tiktoken` para los 10 incidentes en JSON indentado, JSON compacto, YAML y CSV, y explica qué formato elegirías al inyectar datos tabulares o logs largos en la ventana de contexto.

#### uv run python -m src.context_audit --compare-formats

==========================================================================
 IMPACTO DEL FORMATO DE DATOS EN LA VENTANA DE CONTEXTO (10 Incidentes)
 Tokenizador activo: tiktoken (o200k_base)
==========================================================================
Formato de Serialización       | Caracteres   | Tokens
--------------------------------------------------------------------------
JSON Indentado (indent=2)      | 2942         | 878 tokens
JSON Compacto (minified)       | 2641         | 728 tokens
YAML Equivalente               | 2579         | 755 tokens
CSV Delimitado por '|'         | 2171         | 617 tokens
--------------------------------------------------------------------------