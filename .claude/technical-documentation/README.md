# Nexora — Technical Design

Source: `Nexora_Specification_and_Technical_Design.docx`, Part II. Version 0.1 Draft. This is the **proposed** design; many choices are still open (see [roadmap-risks-decisions.md](roadmap-risks-decisions.md#open-decisions)).

| File | Contents |
|---|---|
| [architecture.md](architecture.md) | Layers, proposed technology, component design (Rayfin UI through Deployment Service) |
| [llm-responsibility-split.md](llm-responsibility-split.md) | What the LLM, MCP tools and deterministic services each own |
| [artifact-contracts.md](artifact-contracts.md) | The artifacts each stage produces, their producers and validators |
| [workflow-and-validation-gates.md](workflow-and-validation-gates.md) | Run state model and gates G1–G6 |
| [sandbox-security-bridge-tables.md](sandbox-security-bridge-tables.md) | Sandbox/promotion, security and data handling, bridge-table design |
| [roadmap-risks-decisions.md](roadmap-risks-decisions.md) | Milestones M1–M7, status tracking, risks, open decisions |

Requirements are in [`../spec/`](../spec/README.md).
