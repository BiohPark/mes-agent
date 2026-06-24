# Sanitized CLI Delegation Notes

Use external CLI delegation only for abstract review. Do not send repository paths, live document names, internal URLs, screenshots, company identifiers, raw logs, or raw fixture contents.

## Allowed Claude Prompt Shape

```powershell
claude --print --output-format json --permission-mode plan --max-budget-usd 1.0 --safe-mode --no-session-persistence 'Sanitized design review only. No repository or company details are included. Review an abstract benchmark for a regulated-document validation assistant. Focus on risks, scoring gaps, and UX observation signals. Do not ask for secrets or external data.'
```

## Allowed agy Prompt Shape

```powershell
agy --print --print-timeout 20s 'Sanitized check only. No repository or company details. For a local benchmark of a regulated-document validation assistant, list UX friction signals a Computer-Use observer should record. Keep answer abstract.'
```

## Current Planning Attempt

During plan creation, the Claude command shape above produced no output within the local wait window and the matching process was stopped. The agy command shape exited with code 0 and no output. Treat both as best-effort only; local repo evidence and user instructions remain authoritative.
