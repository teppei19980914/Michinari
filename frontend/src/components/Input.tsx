import type { InputHTMLAttributes } from 'react'

export function Input({ className = '', ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={`rounded-md border border-border-strong px-3 py-2 text-sm focus:border-accent focus:outline-none ${className}`}
      {...rest}
    />
  )
}
