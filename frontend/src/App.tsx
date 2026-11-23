import { type ReactNode, useEffect, useRef } from 'react'
import { type ChatStatus, useChat } from './chat/useChat'
import { AssistantAnswer } from './components/AssistantAnswer'
import { Composer } from './components/Composer'
import { HealthBanner } from './components/HealthBanner'
import { LanguageSwitcher } from './components/LanguageSwitcher'
import { MascotAvatar, type Mood } from './components/MascotAvatar'
import { MESSAGES, type Messages } from './i18n/messages'
import { useLanguage } from './i18n/useLanguage'

export function App() {
  const [language, setLanguage] = useLanguage()
  const text = MESSAGES[language]
  const chat = useChat(language)
  const endOfChat = useRef<HTMLDivElement>(null)
  const thinking = chat.status.state === 'thinking'

  // Keep the newest message in view.
  // biome-ignore lint/correctness/useExhaustiveDependencies: scroll whenever the chat changes
  useEffect(() => {
    endOfChat.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [chat.entries, chat.status])

  return (
    <div className="flex h-svh flex-col bg-amber-50 text-stone-800 dark:bg-stone-900 dark:text-stone-100">
      <header className="border-b border-amber-200 bg-white/80 backdrop-blur dark:border-stone-700 dark:bg-stone-900/80">
        <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3">
          <MascotAvatar mood={moodFor(chat.status)} size={44} />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-lg font-semibold">{text.title}</h1>
            <p className="truncate text-sm text-stone-500 dark:text-stone-400">{text.subtitle}</p>
          </div>
          <LanguageSwitcher language={language} onChange={setLanguage} />
          <button
            type="button"
            onClick={chat.reset}
            disabled={chat.entries.length === 0}
            className="hidden rounded-full border border-stone-300 px-3 py-1 text-xs font-medium hover:bg-stone-100 disabled:opacity-40 sm:block dark:border-stone-600 dark:hover:bg-stone-800"
          >
            {text.newChat}
          </button>
        </div>
      </header>

      <HealthBanner degradedLabel={text.degraded} unreachableLabel={text.serverUnreachable} />

      <main className="flex-1 overflow-y-auto">
        <ol aria-live="polite" className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6">
          <AssistantBubble>
            <p>{text.greeting}</p>
          </AssistantBubble>
          {chat.entries.map((entry) =>
            entry.role === 'user' ? (
              <li key={entry.id} className="flex justify-end">
                <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-amber-500 px-4 py-2.5 text-white shadow-sm">
                  {entry.text}
                </p>
              </li>
            ) : (
              <AssistantBubble key={entry.id}>
                <AssistantAnswer response={entry.response} language={entry.response.language} />
              </AssistantBubble>
            ),
          )}
          {thinking && (
            <AssistantBubble>
              <p className="text-stone-500 italic dark:text-stone-400">{text.thinking}</p>
            </AssistantBubble>
          )}
          {chat.status.state === 'error' && (
            <AssistantBubble>
              <ErrorMessage status={chat.status} text={text} onRetry={chat.retry} />
            </AssistantBubble>
          )}
        </ol>
        <div ref={endOfChat} />
      </main>

      <footer className="border-t border-amber-200 bg-white/80 backdrop-blur dark:border-stone-700 dark:bg-stone-900/80">
        <div className="mx-auto max-w-3xl px-4 py-3">
          <Composer
            placeholder={text.placeholder}
            sendLabel={text.send}
            disabled={thinking}
            onSend={chat.send}
          />
        </div>
      </footer>
    </div>
  )
}

function AssistantBubble({ children }: { children: ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-white px-4 py-3 shadow-sm ring-1 ring-amber-100 dark:bg-stone-800 dark:ring-stone-700">
        {children}
      </div>
    </li>
  )
}

function ErrorMessage({
  status,
  text,
  onRetry,
}: {
  status: Extract<ChatStatus, { state: 'error' }>
  text: Messages
  onRetry: () => void
}) {
  const message =
    status.error.status === 0
      ? text.serverUnreachable
      : `${text.serverError} ${status.error.message}`
  return (
    <div className="space-y-2">
      <p className="text-red-700 dark:text-red-300">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-full bg-stone-800 px-3 py-1 text-sm font-medium text-white hover:bg-stone-700 dark:bg-stone-200 dark:text-stone-900"
      >
        {text.retry}
      </button>
    </div>
  )
}

function moodFor(status: ChatStatus): Mood {
  switch (status.state) {
    case 'thinking':
      return 'thinking'
    case 'error':
      return 'worried'
    default:
      return 'idle'
  }
}
