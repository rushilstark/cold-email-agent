import clsx from 'clsx'

interface ScoreBarProps {
  score: number
  showLabel?: boolean
}

export default function ScoreBar({ score, showLabel = true }: ScoreBarProps) {
  const clamped = Math.min(100, Math.max(0, score))

  const barColor = clsx({
    'bg-emerald-500': clamped >= 75,
    'bg-amber-400': clamped >= 50 && clamped < 75,
    'bg-red-400': clamped < 50,
  })

  const textColor = clsx('text-xs font-semibold tabular-nums', {
    'text-emerald-700': clamped >= 75,
    'text-amber-600': clamped >= 50 && clamped < 75,
    'text-red-600': clamped < 50,
  })

  return (
    <div className="flex items-center gap-2 w-full min-w-[80px]">
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={clsx('h-full rounded-full transition-all duration-700 ease-out', barColor)}
          style={{ width: `${clamped}%` }}
        />
      </div>
      {showLabel && <span className={textColor}>{clamped}</span>}
    </div>
  )
}
