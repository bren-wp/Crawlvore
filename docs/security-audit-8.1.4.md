# Runtime security audit — Bandit 1.9.4

Scope: Python runtime at commit 4cd91330; tests and build tools excluded.
Reproduced on Windows and in Linux Quality CI: 5 low, 0 medium, 0 high.
This is a bounded static-analysis review, not a full application security sign-off.

| Finding | Review and disposition |
| --- | --- |
| B404 native_vault.py | subprocess is needed to call Linux Secret Service. No shell; argument list; credential via stdin. Hardened by restricting the executable to /usr/bin/secret-tool and explicitly allowlisting operations. Native Linux regression verification required. |
| B105 registry.py TOKEN_URL | Public OAuth endpoint URL, not a credential. |
| B105 registry.py Client.token | Empty initial token state, not a hardcoded credential. Token obtained at runtime from authorized OAuth response. |
| B406 registry_export.py | XMLGenerator writes XML; no untrusted XML parsing or entity resolution. Data values use escaped XML output and JSON encoding. |
| B101 tvrtk_scraper.py | Fixed: explicit RuntimeError on browser smoke mismatch, including optimized Python builds. |

No blanket scanner suppressions added. Existing exclusions and other prior
nosec annotations are outside this five-finding review and require separate
assessment. Dependency, native, frontend, and manual security acceptance remain
independent gates.
