import * as React from 'react'

import { cn } from '@/lib/utils'

type IconProps = React.SVGProps<SVGSVGElement>

/**
 * Brand marks that Lucide no longer ships (removed for trademark reasons).
 * Kept as minimal inline SVGs so we avoid an extra icon dependency.
 */

export function GitHubMark({ className, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className={cn('h-4 w-4', className)}
      {...props}
    >
      <path d="M12 .5C5.73.5.5 5.74.5 12.02c0 5.1 3.29 9.42 7.86 10.95.58.11.79-.25.79-.56 0-.28-.01-1.02-.02-2-3.2.7-3.88-1.54-3.88-1.54-.53-1.35-1.28-1.71-1.28-1.71-1.05-.72.08-.71.08-.71 1.16.08 1.77 1.2 1.77 1.2 1.03 1.77 2.7 1.26 3.36.96.1-.75.4-1.26.73-1.55-2.55-.29-5.24-1.28-5.24-5.69 0-1.26.45-2.29 1.19-3.09-.12-.29-.52-1.46.11-3.05 0 0 .97-.31 3.18 1.18a11 11 0 0 1 5.8 0c2.2-1.49 3.17-1.18 3.17-1.18.63 1.59.23 2.76.11 3.05.74.8 1.19 1.83 1.19 3.09 0 4.42-2.69 5.39-5.25 5.68.41.36.78 1.06.78 2.14 0 1.55-.02 2.8-.02 3.18 0 .31.21.68.8.56A11.53 11.53 0 0 0 23.5 12.02C23.5 5.74 18.27.5 12 .5Z" />
    </svg>
  )
}

export function ArxivMark({ className, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cn('h-4 w-4', className)}
      {...props}
    >
      <path
        d="M4 4h9a5 5 0 0 1 0 10H8l7 6M8 14V4"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function HuggingFaceMark({ className, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      className={cn('h-4 w-4', className)}
      {...props}
    >
      <path d="M12 2a9 9 0 0 0-9 9c0 1.68.46 3.25 1.26 4.6a2 2 0 1 0 2.35 2.9A8.96 8.96 0 0 0 12 20c1.5 0 2.92-.37 4.17-1.02a2 2 0 1 0 2.4-2.86A8.96 8.96 0 0 0 21 11a9 9 0 0 0-9-9Zm-3 8a1.25 1.25 0 1 1 0 2.5A1.25 1.25 0 0 1 9 10Zm6 0a1.25 1.25 0 1 1 0 2.5A1.25 1.25 0 0 1 15 10Zm-6.1 4.4c.28-.2.66-.13.86.14.5.68 1.3 1.1 2.24 1.1s1.74-.42 2.24-1.1a.62.62 0 1 1 1 .73A3.86 3.86 0 0 1 12 17a3.86 3.86 0 0 1-3.24-1.73.62.62 0 0 1 .14-.87Z" />
    </svg>
  )
}
