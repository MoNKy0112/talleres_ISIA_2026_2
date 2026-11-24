---
name: hexagonal-architecture
description: Enforces IncidentOps hexagonal import boundaries, shared use cases, adapter parity, and Ruff checks.
---

# IncidentOps Hexagonal Architecture

Use this skill when implementing, refactoring, or reviewing code under `src/`.
Follow `.specify/memory/constitution.md` and ADR-003. Keep domain policy in one
place and direct dependencies inward.

## Layer boundaries

| Layer | May import | Must not import |
| --- | --- | --- |
| `src/domain/` | Python standard library and other `src.domain` modules | Frameworks, HTTP/transport code, database drivers, ORMs, application, or adapters |
| `src/application/` | Python standard library and `src.domain` | Frameworks, HTTP/CLI adapters, database drivers, ORMs, or outbound adapters |
| `src/adapters/inbound/` | Its transport framework/schema, `src.application`, and `src.adapters.outbound.factory` | Database drivers or concrete repositories directly |
| `src/adapters/outbound/` | `src.application` ports, domain types, and the selected persistence driver | Inbound adapters and transport-specific behavior |

`src/application/ports.py` owns secondary ports declared with `typing.Protocol`.
Outbound persistence adapters implement `IncidentRepositoryPort`. Inbound code
obtains persistence through `src.adapters.outbound.factory`; it must not construct
or import a concrete repository or database driver itself. Keep `DATABASE_URL`
handling at the composition/factory boundary, never in domain rules or use cases.

The domain must stay deterministic and free of infrastructure concerns. Application
services coordinate use cases and depend on abstractions, not adapters. Adapters
translate inputs and outputs; they do not implement business rules.

## Primary-adapter parity

REST and CLI MUST call the same application use case, such as
`IncidentService.triage_incident(...)`, for equivalent requests. Do not duplicate
classification, validation policy, routing, or response decisions in either
adapter. When adding or changing an inbound adapter:

1. Reuse the existing application service and domain behavior.
2. Keep transport parsing, serialization, and transport-specific error mapping at
   the adapter boundary.
3. Add acceptance coverage proving equivalent valid input produces equivalent
   domain results across REST and CLI, and that invalid input follows the shared
   validation policy.

## Ruff import-boundary enforcement

Ruff is the static gate for both ordinary lint and layer boundaries. Keep this
selection in `pyproject.toml`:

```toml
[tool.ruff.lint]
select = ["E4", "E7", "E9", "F", "TID"]
```

The selected `TID` rules include TID251 and TID252. Add hierarchical `ruff.toml`
files at `src/domain/`, `src/application/`, and `src/adapters/inbound/`. Each file
must extend the repository `pyproject.toml` (use the relative path from that
directory), retain the selected rules, set
`ban-relative-imports = "parents"` under `[lint.flake8-tidy-imports]`, and define
layer-specific `[lint.flake8-tidy-imports.banned-api]` entries for forbidden
imports. TID251 requires those `banned-api` entries; configure them so domain and
application imports cannot cross outward, and inbound adapters cannot import
drivers or concrete repositories. Keep the approved outbound factory usable from
inbound code.

Run the boundary and lint check from the repository root:

```bash
uv run ruff check src/
```

Do not claim the architecture is statically enforced unless the relevant
`ruff.toml` files contain the bans for the layer being changed.
