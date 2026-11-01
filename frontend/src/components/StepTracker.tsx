import React from 'react'
import { Check } from 'lucide-react'

/**
 * Numbered progress card (01 → 02 → 03).
 * Only used where the content really is a sequence.
 * `current` is the index of the active step; earlier steps show as done.
 */
export function StepTracker({ steps, current }: { steps: string[]; current: number }) {
  return (
    <ol
      className="grid gap-2 rounded-card bg-white p-4 shadow-card"
      style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}
      aria-label="Progress"
    >
      {steps.map((label, i) => {
        const done = i < current
        const active = i === current
        return (
          <li key={label} className="relative" aria-current={active ? 'step' : undefined}>
            <span
              className={`flex h-9 w-9 items-center justify-center rounded-xl text-[12px] font-extrabold ${
                active
                  ? 'bg-cyan text-white'
                  : done
                  ? 'bg-cyan-soft text-cyan-deep'
                  : 'bg-mist text-[#9FB0C6]'
              }`}
            >
              {done ? <Check size={16} strokeWidth={3} /> : String(i + 1).padStart(2, '0')}
            </span>
            {i < steps.length - 1 && (
              <span
                aria-hidden
                className={`absolute left-11 right-0 top-[17px] h-0.5 rounded ${done ? 'bg-cyan/50' : 'bg-line'}`}
              />
            )}
            <span
              className={`mt-2 block text-[12px] font-bold leading-tight ${
                active ? 'text-navy' : done ? 'text-cyan-deep' : 'text-muted'
              }`}
            >
              {label}
            </span>
          </li>
        )
      })}
    </ol>
  )
}
