import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

/**
 * Shadcn's `cn` helper: merge conditional class names and de-duplicate
 * conflicting Tailwind utilities (last one wins).
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}
