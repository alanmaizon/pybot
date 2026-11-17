# Security policy

## Scope and security assumptions

PyBot is a static GitHub Pages application. Conversation memory, structured memory, uploaded
documents, and diagnostics are intended to remain in the browser. The application does not
provide a backend for processing user content.

The optional Python tool is **not a secure sandbox**. It now uses an explicit AST interpreter and
rejects imports, attribute access, comprehensions, loops, and unsupported syntax. This prevents
the previous object-introspection escape from reaching Python `exec`/`eval`, but browser/Pyodide
isolation and denial-of-service resistance are not equivalent to an OS-level sandbox. Do not use
it for secrets, hostile workloads, or untrusted automation.

Uploaded documents are treated as untrusted text. They are parsed locally, never executed, and
must be explicitly selected before document tools can read or search them. Files marked for local
persistence remain in browser storage until deleted or site data is cleared.

## Reporting a vulnerability

Please report security issues privately through GitHub's repository security advisory workflow when
available. Include a description, affected version or commit, reproduction steps, impact, and any
safe mitigation. Do not include real personal data, credentials, or confidential documents in a
report.

Security fixes should include a regression test and should not claim a stronger isolation boundary
than the browser architecture can provide.
