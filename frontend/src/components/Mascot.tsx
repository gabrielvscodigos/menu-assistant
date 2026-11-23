// The waiter mascot: the project's character artwork, shown as a static image. `full`
// shows him standing with his tray; `bust` shows head and shoulders on a color tile, for
// avatars. The images are generated from art/waiter-source.png by art/process-artwork.ps1.
import waiterAvatar from '../assets/waiter-avatar.png'
import waiterFull from '../assets/waiter-full.png'

export type MascotVariant = 'bust' | 'full'

interface MascotProps {
  /** Height in pixels. */
  size?: number
  variant?: MascotVariant
  /** Accessible name; leave it out for a decorative copy (hidden from screen readers). */
  label?: string
  /** Extra classes, e.g. responsive sizes that override `size` on larger screens. */
  className?: string
}

// waiter-full.png is 600 x 480.
const FULL_ASPECT_RATIO = 600 / 480

export function Mascot({ size = 64, variant = 'bust', label, className = '' }: MascotProps) {
  const full = variant === 'full'
  return (
    <img
      src={full ? waiterFull : waiterAvatar}
      alt={label ?? ''}
      aria-hidden={label ? undefined : true}
      width={full ? Math.round(size * FULL_ASPECT_RATIO) : size}
      height={size}
      data-variant={variant}
      draggable={false}
      className={`shrink-0 select-none ${full ? '' : 'rounded-xl bg-red-50'} ${className}`}
    />
  )
}
