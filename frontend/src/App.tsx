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
    <div className="flex h-svh flex-col bg-white font-sans text-sm text-stone-800 dark:bg-stone-900 dark:text-stone-100">
      <header className="border-b border-stone-200 bg-white/90 backdrop-blur dark:border-stone-700 dark:bg-stone-900/90">
        <div className="mx-auto flex max-w-3xl items-center gap-2.5 px-3 py-2 sm:gap-3 sm:px-4 sm:py-3">
          <Mascot
            size={44}
            label={text.mascotLabel}
            className="ring-2 ring-red-600 ring-offset-2 sm:size-12 dark:ring-offset-stone-900"
          />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-base font-bold text-stone-900 sm:text-lg dark:text-stone-100">
              {text.title}
            </h1>
            <OnlineStatus label={text.subtitle} />
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
              <p className="text-white/85 italic">{text.thinking}</p>
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

      <footer className="border-t border-stone-200 bg-white/90 backdrop-blur dark:border-stone-700 dark:bg-stone-900/90">
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
            <li>
              <div className="max-w-xl">
                <DishCards
                  dishes={entry.response.sources}
                  language={entry.response.language}
                  quantities={selection.quantities}
                  onToggle={selection.toggle}
                  onAdd={selection.add}
                  onRemove={selection.remove}
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

/** Status under the title, with a green "online" dot. */
function OnlineStatus({ label }: { label: string }) {
  return (
    <p className="flex items-center gap-1.5 text-xs leading-4 text-stone-500 dark:text-stone-400">
      {/* Nudged 1px down to line up with the lowercase letters, not the line box. */}
      <span
        aria-hidden="true"
        className="size-2 shrink-0 translate-y-px rounded-full bg-emerald-500"
      />
      <span className="truncate">{label}</span>
    </p>
  )
}

/** A message from the waiter: a red bubble on the left. */
function AssistantBubble({ children }: { children: ReactNode }) {
  return (
    <li className="flex justify-start">
      <div className="max-w-[92%] rounded-2xl rounded-tl-md bg-red-600 px-4 py-3 text-white">
        {children}
      </div>
    </li>
  )
}

function UserBubble({ children }: { children: ReactNode }) {
  return (
    <li className="flex justify-end">
      <div className="max-w-[85%] rounded-2xl rounded-br-md bg-stone-900 px-4 py-3 text-white dark:bg-stone-700">
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
        className="rounded-xl bg-white px-3 py-2 text-sm font-normal text-stone-700 dark:bg-stone-900 dark:text-stone-200"
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
      <p>{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-full bg-white px-3 py-1 text-sm font-semibold text-red-700 hover:bg-red-50"
      >
        {text.retry}
      </button>
    </div>
  )
}
