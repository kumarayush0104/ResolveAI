import React from 'react'

export function Card({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`rounded-card bg-white p-4 shadow-card ${className}`}>{children}</div>
}
