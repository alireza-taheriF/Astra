/**
 * TypeScript models for Astra data.
 *
 * The capability-summary types below mirror, field-for-field, the JSON snapshot
 * produced by the backend capability engine (Phase 2) and persisted into
 * `repositories.astra_capability_summary`. Keep them in sync with that engine's
 * output shape.
 */

/** How deeply a library is used within a file/repo. */
export type LibraryDepth = 'kernel_authoring' | 'api_usage' | 'import_only'

/** The four scoring categories the engine attributes weight to. */
export type ScoreCategory = 'ml_infra' | 'systems' | 'data' | 'web'

/** Per-library rollup within a repository's capability summary. */
export interface LibrarySignal {
  depth: LibraryDepth
  weight: number
  file_count: number
}

/**
 * Exact shape of `repositories.astra_capability_summary` (JSONB).
 *
 * Mirrors the dict returned by `capability_engine.analyze_repository`.
 */
export interface AstraCapabilitySummary {
  analyzed_at: string // ISO-8601 UTC
  files_analyzed: number
  avg_cyclomatic_complexity: number
  max_ast_depth: number
  library_signals: Record<string, LibrarySignal>
  boilerplate_ratio: number // 0.0 – 1.0
  subscore_contributions: Record<ScoreCategory, number>
}

/** A repositories row, narrowed to what the dashboard renders. */
export interface RepositoryRow {
  id: string
  repo_full_name: string
  is_fork: boolean
  primary_language: string | null
  astra_capability_summary: AstraCapabilitySummary
  last_analyzed_at: string | null
}

/** Human-facing subscore breakdown stored on a capability_scores row. */
export interface SubscoreBreakdown {
  ml_infra?: number
  systems?: number
  research_alignment?: number
  [key: string]: number | undefined
}

/** A capability_scores row, narrowed to dashboard fields. */
export interface CapabilityScoreRow {
  astra_score: number
  percentile: number | null
  score_version: string
  subscore_breakdown: SubscoreBreakdown
  is_current: boolean
  computed_at: string
}

/** A connected external identity. */
export type IdentityProvider = 'github' | 'arxiv' | 'huggingface'

export interface IdentityRow {
  id: string
  provider: IdentityProvider
  provider_username: string
  verified: boolean
}

/**
 * Derived, display-ready subscore used by the UI (label + value + percentile).
 * Not persisted; assembled in the page from the rows above.
 */
export interface DisplaySubscore {
  key: string
  label: string
  value: number // 0 – 100 for bar fill
  percentile: number | null
  trend: number[] // sparkline points, most-recent last
}
