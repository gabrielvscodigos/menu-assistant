// Placeholder for the waiter mascot. Step 4 replaces the drawing with an animated SVG;
// the `mood` prop is already the interface the rest of the app uses.
export type Mood = 'idle' | 'thinking' | 'talking' | 'worried'

interface MascotAvatarProps {
  mood: Mood
  size?: number
}

export function MascotAvatar({ mood, size = 40 }: MascotAvatarProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      role="img"
      aria-label="Waiter"
      data-mood={mood}
      className={mood === 'thinking' ? 'animate-pulse' : undefined}
    >
      <circle cx="20" cy="18" r="13" fill="#fde7c7" stroke="#78350f" strokeWidth="1.5" />
      <circle cx="15.5" cy="16" r="1.6" fill="#292524" />
      <circle cx="24.5" cy="16" r="1.6" fill="#292524" />
      <path
        d={mood === 'worried' ? 'M15 23 Q20 20 25 23' : 'M15 21 Q20 25 25 21'}
        stroke="#292524"
        strokeWidth="1.5"
        fill="none"
        strokeLinecap="round"
      />
      <path d="M14 34 L20 31 L14 28 Z M26 34 L20 31 L26 28 Z" fill="#b91c1c" />
      <circle cx="20" cy="31" r="1.5" fill="#7f1d1d" />
    </svg>
  )
}
