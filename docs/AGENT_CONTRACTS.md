# Agent Contracts

> **Placeholder** — schemas will be locked Wednesday morning during SYNC 1 with the backend track.

These contracts define the data shapes shared between the agent backend and the static viewer:

| Artifact | Format | Consumer |
|----------|--------|----------|
| `AuditChainEvent` | JSON Lines entry | Viewer audit timeline |
| `StructuredFinding` | JSON in chat | Captain (internal) |
| `CaptainVerdict` | JSON in chat | Viewer summary tab |
| `LiaisonReport` | Markdown | Viewer summary tab |
| `CaseFile` | JSON file | Viewer (primary input) |

**Status:** Awaiting `docs/AGENT_CONTRACTS.md` from backend track. After lock, any change requires both tracks to sync.
