import clsx from 'clsx'

interface TierBadgeProps {
  tier: string
  size?: 'sm' | 'md'
}

export default function TierBadge({ tier, size = 'sm' }: TierBadgeProps) {
  const label = tier ? tier.replace('_', ' ').toUpperCase() : 'UNSCORED'

  const styles = clsx(
    'inline-flex items-center font-semibold rounded-full',
    size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-3 py-1 text-sm',
    {
      'bg-emerald-100 text-emerald-700': tier === 'tier1',
      'bg-amber-100 text-amber-700': tier === 'tier2',
      'bg-red-100 text-red-700': tier === 'tier3',
      'bg-gray-100 text-gray-500': !tier || (tier !== 'tier1' && tier !== 'tier2' && tier !== 'tier3'),
    },
  )

  return <span className={styles}>{label}</span>
}
