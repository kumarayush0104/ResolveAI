import React from 'react'

interface CardProps {
  children: React.ReactNode
  className?: string
  gradient?: boolean
  onClick?: () => void
}

export function Card({ children, className = '', gradient = false, onClick }: CardProps) {
  if (gradient) {
    return (
      <div
        onClick={onClick}
        className={`hero-gradient rounded-3xl shadow-float text-white ${onClick ? 'cursor-pointer' : ''} ${className}`}
      >
        {children}
      </div>
    )
  }
  return (
    <div
      onClick={onClick}
      className={`bg-white rounded-2xl shadow-card ${onClick ? 'cursor-pointer' : ''} ${className}`}
    >
      {children}
    </div>
  )
}
