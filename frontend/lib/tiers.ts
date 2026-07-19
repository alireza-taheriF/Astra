/**
 * Score → tier mapping.
 *
 * Mirrors the backend badge renderer's chess-rating tiers so the passport UI
 * and the embeddable badge always agree on color and label.
 */
export interface ScoreTier {
  label: string
  /** Solid accent color for the tier (used for ring stroke, chips). */
  color: string
}

const TIERS: ReadonlyArray<{ min: number; label: string; color: string }> = [
  { min: 2400, label: 'Grandmaster', color: '#FFD700' },
  { min: 2000, label: 'Master', color: '#A855F7' },
  { min: 1600, label: 'Expert', color: '#3B82F6' },
  { min: 0, label: 'Apprentice', color: '#64748B' },
]

export function tierForScore(score: number): ScoreTier {
  for (const tier of TIERS) {
    if (score >= tier.min) {
      return { label: tier.label, color: tier.color }
    }
  }
  return { label: 'Apprentice', color: '#64748B' }
}
