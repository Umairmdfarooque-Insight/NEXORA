// Shapes returned by the Nexora API (see .claude/tasks/CONTRACTS.md).

export interface SqlEndpoint {
  server: string;
  database: string;
}

export interface RunScope {
  workspace_id: string;
  workspace_name: string | null;
  lakehouse_id: string;
  lakehouse_name: string;
  schemas: string[];
  sql_endpoint: SqlEndpoint | null;
}

export interface HistoryEntry {
  from: string | null;
  to: string;
  at: string;
  reason: string;
  actor: string;
}

export interface Principal {
  oid: string;
  upn: string;
  name: string;
}

export interface RunDetail {
  run_id: string;
  prompt: string;
  subject_area: string | null;
  desired_outputs: string[];
  constraints: string[];
  state: string;
  resume_state: string | null;
  scope: RunScope | null;
  created_by: Principal | null;
  created_at: string;
  updated_at: string;
  history: HistoryEntry[];
  next_action: string;
  open_questions: OpenQuestion[];
  warnings: string[];
  artifacts: Record<string, ArtifactRef>;
  contract: Contract | null;
  data_gaps: DataGap[];
}

export interface DataGap {
  gap_id: string;
  description: string;
  raised_by: string;
  at: string;
  from_state: string;
}

export interface ArtifactRef {
  path: string;
  version: number;
  hash: string;
  status: string;
  updated_at: string;
}

export interface ExpectedExample {
  description: string;
  value: number | string | null;
}

export interface Kpi {
  name: string;
  formula_intent: string | null;
  grain: string | null;
  filters: string[];
  time_logic: string | null;
  exclusions: string[];
  currency: string | null;
  expected_examples: ExpectedExample[];
  status: string;
  rationale: string | null;
}

export interface ContractQuestion {
  id: string;
  text: string;
  blocking: boolean;
  reason: string | null;
  source: string;
  status: "open" | "answered" | "dismissed";
  answer: string | null;
  dismiss_reason: string | null;
}

export interface LockedFact {
  id: string;
  text: string;
  source_question_id: string | null;
  locked_at: string;
}

export interface Contract {
  run_id: string;
  version: number;
  status: "draft" | "approved";
  domain: string | null;
  business_objective: string;
  grain: string | null;
  entities: string[];
  kpis: Kpi[];
  dimensions: string[];
  filters: string[];
  currency: string | null;
  exclusions: string[];
  security: { description: string; applies_to: string[] }[];
  open_questions: ContractQuestion[];
  locked_facts: LockedFact[];
  assumptions: string[];
}

/** Fields of a KPI the owner may edit; only the fields sent change. */
export type KpiChanges = Partial<
  Pick<
    Kpi,
    "formula_intent" | "grain" | "time_logic" | "currency" | "filters" | "exclusions" | "rationale"
  >
>;

export interface GateCheck {
  id: string;
  description: string;
  status: "pass" | "fail" | "warning";
  evidence: Record<string, unknown>;
}

export interface GateResult {
  gate: string;
  artifact: string;
  artifact_hash: string;
  passed: boolean;
  checked_at: string;
  checks: GateCheck[];
}

export type ApprovalAction = "ACCEPT" | "EDIT" | "REJECT" | "EXPLAIN" | "REGENERATE";

export interface ApprovalRecord {
  approval_id: string;
  run_id: string;
  artifact: string;
  artifact_version: number;
  artifact_hash: string;
  action: ApprovalAction;
  role: string | null;
  user: { oid: string; upn: string };
  at: string;
  comment: string | null;
  gate_result_ref: string | null;
}

export interface Explanation {
  kpis: { name: string; status: string; rationale: string }[];
  questions: { id: string; text: string; rationale: string }[];
}

export interface ApprovalBody {
  artifact: "BusinessContract" | "MetadataInventory";
  action: ApprovalAction;
  expected_hash: string;
  comment?: string;
  edits?: { kpis: Record<string, KpiChanges> };
}

export interface ApprovalResult {
  approval: ApprovalRecord;
  run: RunDetail;
  gate_result: GateResult | null;
  explanation: Explanation | null;
}

export interface QuestionResult {
  run: RunDetail;
  contract: Contract;
}

export interface CompileResult extends QuestionResult {
  blocking_questions: number;
}

export interface Me {
  oid: string;
  upn: string;
  name: string;
  roles: string[];
}

export interface OpenQuestion {
  id: string;
  text: string;
  blocking: boolean;
  reason: string | null;
  source: string;
}

export interface RunSummary {
  run_id: string;
  state: string;
  prompt_preview: string;
  created_at: string;
  created_by: Record<string, unknown> | null;
}

export interface RunList {
  items: RunSummary[];
  total: number;
}

export interface Workspace {
  id: string;
  display_name: string;
  type: string;
}

export interface Lakehouse {
  id: string;
  display_name: string;
  workspace_id: string;
  sql_endpoint: SqlEndpoint | null;
}

export interface CreateRunBody {
  prompt: string;
  subject_area?: string;
  desired_outputs: string[];
  constraints: string[];
}

export interface InventoryColumn {
  name: string;
  data_type: string | null;
  nullable: boolean | null;
  description: string | null;
}

export interface ColumnProfile {
  null_count: number | null;
  distinct_count: number | null;
  is_key_candidate: boolean;
  is_unique: boolean | null;
  duplicate_count: number | null;
  min: string | number | null;
  max: string | number | null;
  approximate: boolean;
  note: string | null;
}

export interface TableProfile {
  status: "ok" | "warning" | "error";
  code: string | null;
  message: string | null;
  row_count: number | null;
  columns: Record<string, ColumnProfile>;
  freshness: {
    column: string | null;
    max_value: string | null;
    age_days: number | null;
    status: "ok" | "unknown";
  } | null;
  warnings: string[];
  evidence: { queries: string[]; profiled_at: string };
}

export interface InventoryTable {
  schema: string;
  table_name: string;
  description: string | null;
  columns: InventoryColumn[];
  profile: TableProfile | null;
  errors: { code: string; message: string }[];
}

export interface RelationshipEvidence {
  id: string;
  from: { table: string; column: string };
  to: { table: string; column: string };
  source: "heuristic" | "llm" | "user";
  type_compatible: boolean | null;
  overlap_pct: number | null;
  orphan_rate: number | null;
  null_rate: number | null;
  cardinality: "one_to_one" | "many_to_one" | "many_to_many" | null;
  confidence: "high" | "medium" | "low" | null;
  evidence: { queries: string[]; computed_at: string };
  status: "candidate" | "rejected";
  rejected_reason: string | null;
  notes: string[];
}

export interface MetadataInventory {
  run_id: string;
  version: number;
  harvested_at: string;
  scope: { workspace_id: string; lakehouse_id: string; schemas: string[] };
  tables: InventoryTable[];
  relationship_evidence: RelationshipEvidence[];
  errors: { table: string; code: string; message: string }[];
  warnings: string[];
}

export interface HarvestResult {
  summary: { tables: number; columns: number; errors: number };
  artifact: { name: string; version: number; hash: string; status: string };
  warnings: string[];
}

export interface StageCounts {
  [key: string]: number | string[];
}

export interface ExceptionResult {
  exception_id: string;
  table: string;
  approved_by: string;
  at: string;
}

export interface ScopeBody {
  workspace_id: string;
  lakehouse_id: string;
}
