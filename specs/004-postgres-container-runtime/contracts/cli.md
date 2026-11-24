# CLI Health Contract

```text
incidentops health
```

- Calls the shared application health use case, which delegates to the
  configured repository.
- Connected database: writes `{"status":"ok","database":"connected"}` to stdout
  and exits `0`.
- Unavailable database or connectivity exception: writes
  `{"status":"error","database":"unavailable"}` to stdout and exits `1`.
- Does not write credentials or raw database exceptions to output.
