import { useEffect, useState } from 'react'
import { getHealth, isAbortError } from '../api/client'

interface HealthBannerProps {
  degradedLabel: string
  unreachableLabel: string
}

/** Checks /health once and explains what is missing (index, Ollama) before the guest asks. */
export function HealthBanner({ degradedLabel, unreachableLabel }: HealthBannerProps) {
  const [problem, setProblem] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    getHealth(controller.signal)
      .then((health) => {
        setProblem(health.status === 'ok' ? null : `${degradedLabel} ${health.detail ?? ''}`)
      })
      .catch((error: unknown) => {
        if (!isAbortError(error)) {
          setProblem(unreachableLabel)
        }
      })
    return () => controller.abort()
  }, [degradedLabel, unreachableLabel])

  if (!problem) {
    return null
  }
  return (
    <div
      role="alert"
      className="border-b border-red-200 bg-red-50 px-4 py-2 text-center text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-200"
    >
      {problem}
    </div>
  )
}
