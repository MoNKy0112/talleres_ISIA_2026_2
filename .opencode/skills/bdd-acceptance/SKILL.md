---
name: bdd-acceptance
description: Writes business-readable Given/When/Then specifications and maps each scenario to isolated pytest acceptance tests.
---

# BDD Acceptance for IncidentOps

Use this skill when writing feature acceptance criteria or their automated
acceptance tests. Keep specifications readable by product, support, and engineering.

## Write scenarios in `spec.md`

- Use Dan North's behavior-focused structure: a scenario title names the behavior;
  **Given** establishes relevant business context, **When** describes one action or
  event, and **Then** states observable business outcomes.
- Use the ubiquitous domain vocabulary: incident, affected service, severity,
  responsible team, duplicate, active incident, and SLA. Avoid Python class/function
  names, module paths, SQL table names, database columns, and implementation steps.
- State only preconditions relevant to the outcome. Keep one business behavior per
  scenario; use `And` for additional outcomes of the same behavior.
- Describe outcomes precisely enough to test, including important boundaries,
  business-visible errors, and differences between individual impact and service-wide
  impact.
- Do not make a scenario prescribe an algorithm, framework, schema, or database query.
  Keep transport-specific details only where the feature itself is about that
  interface; keep the business behavior independent of transport.

Example:

```gherkin
### Scenario: An individual account lockout is not treated as a service-wide outage

Given a customer's account is locked
When the customer says they need access today
Then the incident is assigned the individual-blockage severity
And the identity team is recommended
```

## Map scenarios to acceptance tests

- Map every scenario in `spec.md` one-to-one to a pytest function named
  `test_bdd_<scenario_name_in_snake_case>` under `tests/`. Do not combine unrelated
  scenarios into one test or leave a scenario without an automated test.
- Each test should follow the same Given/When/Then phases: arrange the scenario
  context, perform one adapter action, and assert observable results. A concise
  test docstring may identify the behavior.
- Exercise REST through `fastapi.testclient.TestClient` and CLI through
  `typer.testing.CliRunner`. Test public adapter behavior, not private implementation
  details.
- For equivalent REST and CLI scenarios, assert parity of the business result while
  allowing interface-specific response/error formatting and exit status.
- When a scenario reads or writes persisted data, use storage isolated to that test:
  inject a test repository through the outbound factory, use an in-memory store or a
  `tmp_path` database, and ensure state cannot leak between tests. Never point an
  acceptance test at a developer, shared, or production database.
- Stateless scenarios must not introduce storage setup. They should exercise the
  shared application behavior through the selected inbound adapter.
- Run the suite from the repository root with `uv run pytest -v`; report failures
  rather than weakening assertions to make implementation pass.
