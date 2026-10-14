# Sandbox, Security and Bridge Tables

## Sandbox and Promotion

1. Create semantic-model and report artifacts in an isolated development or sandbox target.
2. Run deterministic checks and reconciliation tests.
3. Present validation evidence and rendered outputs in Rayfin.
4. Capture approval and artifact hashes.
5. Promote approved artifacts to the selected higher environment using controlled deployment services.
6. Run smoke tests and record the deployment outcome.
7. On failure, stop promotion and restore or retain the last approved state.

## Security and Data Handling

- Use Entra authentication for Rayfin users and managed identities for service-to-service operations where supported.
- Authorize access by workspace, Lakehouse and deployment target.
- Store secrets in Key Vault; do not place credentials in prompts or artifact files.
- Send the minimum required metadata and profile summaries to the model endpoint.
- Apply tenant/workspace scoping to caches and artifacts.
- Record who approved each business contract, semantic model, report and deployment.
- Use RLS requirements from the approved contract; do not infer security policy without approval.

## Bridge-Table Design

When two entities have a many-to-many relationship, the planning engine must decide one of two things:
- whether an existing mapping table can be used
- whether an approved bridge must be created

Approving the design does not by itself guarantee that mapping logic exists. Generation proceeds only when keys or approved derivation rules are available.

| Situation | System Response |
|---|---|
| Existing Product-Promotion mapping table | Validate duplicates and key coverage, then use it as the bridge if approved. |
| No physical mapping table, but deterministic derivation rule exists | Generate or invoke an approved data-engineering artifact, validate it and reference it from the semantic model. |
| Mapping depends on undocumented business judgement | Stop and request mapping rules or a maintained reference dataset. |
| Bridge contains duplicates | Deduplicate only under an approved deterministic rule; otherwise fail validation. |
| Bridge changes after report generation | Mark semantic model and report stale; regenerate or revalidate impacted artifacts. |
