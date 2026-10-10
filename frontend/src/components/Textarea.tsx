import type { TextareaHTMLAttributes } from 'react'

export function Textarea({ className = '', ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={`rounded-md border border-border-strong px-3 py-2 text-sm focus:border-accent focus:outline-none ${className}`}
      {...rest}
    />
  )
}
