import { type ReactNode, useEffect, useRef } from 'react'
import { type ChatEntry, type ChatStatus, useChat } from './chat/useChat'
import { type Selection, useSelection } from './chat/useSelection'
import { AssistantAnswer } from './components/AssistantAnswer'
import { Composer } from './components/Composer'
import { DishCards } from './components/DishCards'
import { HealthBanner } from './components/HealthBanner'
import { LanguageSwitcher } from './components/LanguageSwitcher'
import { Mascot } from './components/Mascot'
import { OrderBar } from './components/OrderBar'
import { OrderSummary } from './components/OrderSummary'
import { MESSAGES, type Messages } from './i18n/messages'
import { useLanguage } from './i18n/useLanguage'

export function App() {
  const [language, setLanguage] = useLanguage()
  const text = MESSAGES[language]
  const chat = useChat(language)
  const selection = useSelection()
  const endOfChat = useRef<HTMLDivElement>(null)
  const thinking = chat.status.state === 'thinking'
  const last = chat.entries.at(-1)

  // Keep the newest message in view.
  // biome-ignore lint/correctness/useExhaustiveDependencies: scroll whenever the chat changes
  useEffect(() => {
    endOfChat.current?.scrollIntoView?.({ behavior: 'smooth', block: 'end' })
  }, [chat.entries, chat.status])

  function startOver() {
    chat.reset()
    selection.clear()
  }

  function order() {
    chat.placeOrder(selection.dishes)
    selection.clear()
  }

  return (
    <div className="flex h-svh flex-col bg-stone-50 text-stone-800 dark:bg-stone-900 dark:text-stone-100">
      <header className="border-b border-red-100 bg-white/90 backdrop-blur dark:border-stone-700 dark:bg-stone-900/90">
        <div className="mx-auto flex max-w-3xl items-center gap-2.5 px-3 py-2 sm:gap-3 sm:px-4 sm:py-3">
          <Mascot size={44} label={text.mascotLabel} className="sm:size-14" />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-base font-semibold sm:text-lg">{text.title}</h1>
            <p className="truncate text-xs text-stone-500 sm:text-sm dark:text-stone-400">
              {text.subtitle}
            </p>
          </div>
          <LanguageSwitcher language={language} onChange={setLanguage} />
          <button
            type="button"
            onClick={startOver}
            disabled={chat.entries.length === 0}
            aria-label={text.newChat}
            title={text.newChat}
            className="flex size-8 items-center justify-center rounded-full border border-stone-300 text-sm hover:bg-stone-100 disabled:opacity-40 sm:h-auto sm:w-auto sm:px-3 sm:py-1 sm:text-xs sm:font-medium dark:border-stone-600 dark:hover:bg-stone-800"
          >
            <span aria-hidden="true" className="sm:hidden">
              ↺
            </span>
            <span className="hidden sm:inline">{text.newChat}</span>
          </button>
        </div>
      </header>

      <HealthBanner degradedLabel={text.degraded} unreachableLabel={text.serverUnreachable} />

      <main className="flex-1 overflow-y-auto overscroll-contain">
        <ol
          aria-live="polite"
          className="mx-auto flex max-w-3xl flex-col gap-3 px-3 py-4 sm:gap-4 sm:px-4 sm:py-6"
        >
          {chat.entries.length === 0 && (
            <li className="flex justify-center" data-testid="welcome-waiter">
              <Mascot variant="full" size={200} className="h-40 w-auto sm:h-[200px]" />
            </li>
          )}
          <AssistantBubble>
            <p>{text.greeting}</p>
          </AssistantBubble>
          {chat.entries.map((entry) => (
            <ChatEntryView
              key={entry.id}
              entry={entry}
              selection={selection}
              onOtherOptions={
                entry === last && !thinking
                  ? () => chat.send(text.otherOptionsQuestion, { otherOptions: true })
                  : undefined
              }
            />
          ))}
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

      <footer className="border-t border-red-100 bg-white/90 backdrop-blur dark:border-stone-700 dark:bg-stone-900/90">
        <div className="mx-auto max-w-3xl space-y-2 px-3 pt-2.5 pb-[max(0.625rem,env(safe-area-inset-bottom))] sm:px-4 sm:py-3">
          <OrderBar
            dishes={selection.dishes}
            language={language}
            onOrder={order}
            onClear={selection.clear}
          />
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

interface ChatEntryViewProps {
  entry: ChatEntry
  selection: Selection
  onOtherOptions?: () => void
}

/** One entry of the conversation: a question, a reply with its dish cards, or an order. */
function ChatEntryView({ entry, selection, onOtherOptions }: ChatEntryViewProps) {
  switch (entry.role) {
    case 'user':
      return (
        <UserBubble>
          <p className="whitespace-pre-wrap">{entry.text}</p>
        </UserBubble>
      )
    case 'assistant':
      return (
        <>
          <AssistantBubble>
            <AssistantAnswer response={entry.response} language={entry.response.language} />
          </AssistantBubble>
          {entry.response.sources.length > 0 && (
            // Cards sit under the reply, aligned with the bubble, not inside it.
            <li className="pl-11">
              <div className="max-w-md">
                <DishCards
                  dishes={entry.response.sources}
                  language={entry.response.language}
                  selected={selection.ids}
                  onToggle={selection.toggle}
                  onOtherOptions={onOtherOptions}
                />
              </div>
            </li>
          )}
        </>
      )
    case 'order':
      return (
        <>
          <UserBubble>
            <OrderSummary dishes={entry.dishes} language={entry.language} />
          </UserBubble>
          <AssistantBubble>
            <OrderConfirmation text={MESSAGES[entry.language]} />
          </AssistantBubble>
        </>
      )
  }
}

/** A message from the waiter, with his avatar beside it. */
function AssistantBubble({ children }: { children: ReactNode }) {
  return (
    <li className="flex items-start gap-2">
      <Mascot size={36} />
      <div className="max-w-[85%] rounded-2xl rounded-tl-sm bg-white px-3.5 py-2.5 shadow-sm ring-1 ring-red-100 sm:px-4 sm:py-3 dark:bg-stone-800 dark:ring-stone-700">
        {children}
      </div>
    </li>
  )
}

function UserBubble({ children }: { children: ReactNode }) {
  return (
    <li className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-red-600 px-3.5 py-2.5 text-white shadow-sm sm:px-4">
        {children}
      </div>
    </li>
  )
}

function OrderConfirmation({ text }: { text: Messages }) {
  return (
    <div className="space-y-2">
      <p>{text.orderConfirmed}</p>
      <p
        role="note"
        className="rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-900 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-100"
      >
        {text.orderNotice}
      </p>
    </div>
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
