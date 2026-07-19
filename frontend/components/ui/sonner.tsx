'use client'

import { Toaster as Sonner, type ToasterProps } from 'sonner'

/**
 * App-wide toast host, themed to the Astra dark palette.
 */
export function Toaster(props: ToasterProps) {
  return (
    <Sonner
      theme="dark"
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast:
            'group toast group-[.toaster]:bg-surface group-[.toaster]:text-foreground group-[.toaster]:border-hairline group-[.toaster]:shadow-lg',
          description: 'group-[.toast]:text-muted-foreground',
          actionButton:
            'group-[.toast]:bg-primary group-[.toast]:text-primary-foreground',
          cancelButton:
            'group-[.toast]:bg-secondary group-[.toast]:text-muted-foreground',
        },
      }}
      {...props}
    />
  )
}
