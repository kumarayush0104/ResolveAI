import React from 'react'

export function LogoMark({ size = 40 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true" className="shrink-0">
      <rect width="48" height="48" rx="14" fill="#0A2A66" />
      <path
        d="M24 9.5 36.5 14v10.2c0 7.1-5.4 12.6-12.5 14.8-7.1-2.2-12.5-7.7-12.5-14.8V14L24 9.5Z"
        fill="#fff"
      />
      <path
        d="m17.8 24.4 4.4 4.4 8.2-9.4"
        fill="none"
        stroke="#0396D8"
        strokeWidth="3.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

export function Logo({ size = 'md', tagline }: { size?: 'sm' | 'md'; tagline?: string }) {
  const mark = size === 'md' ? 44 : 38
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark size={mark} />
      <span className="flex flex-col leading-none">
        <span className={`font-extrabold tracking-tight text-navy ${size === 'md' ? 'text-[26px]' : 'text-[22px]'}`}>
          Resolve<span className="text-cyan">AI</span>
        </span>
        {tagline && <span className="mt-1 text-[11px] font-semibold text-muted">{tagline}</span>}
      </span>
    </span>
  )
}
