import type { AskResponse, Language } from '../api/client'
import { type Inline, parseAnswer, withoutCardItems } from '../chat/answerText'
import { LABELS } from '../i18n/labels'
import { MESSAGES } from '../i18n/messages'

interface AssistantAnswerProps {
  response: AskResponse
  language: Language
}

/** One reply: the text (with dish chips), what was avoided, and the staff notice. */
export function AssistantAnswer({ response, language }: AssistantAnswerProps) {
  const text = MESSAGES[language]
  const labels = LABELS[language]
  // Dishes shown as cards below are left out of the text's lists (no double listing).
  const blocks = withoutCardItems(
    parseAnswer(response.answer, response.candidates),
    new Set(response.sources.map((dish) => dish.id)),
  )
  const restrictions = response.applied_restrictions
  const avoiding = [
    ...restrictions.exclude_allergens.map((allergen) => labels.allergens[allergen]),
    ...restrictions.exclude_ingredients,
    ...restrictions.require_flags.map((flag) => labels.diets[flag]),
  ]

  return (
    <div className="space-y-3">
      <div className="space-y-2 leading-relaxed">
        {blocks.map((block, index) => {
          const key = `${block.type}-${index}`
          if (block.type === 'paragraph') {
            return (
              <p key={key}>
                {block.lines.map((line, lineIndex) => (
                  // biome-ignore lint/suspicious/noArrayIndexKey: lines never reorder
                  <span key={lineIndex} className="block">
                    <InlineParts parts={line} />
                  </span>
                ))}
              </p>
            )
          }
          const List = block.ordered ? 'ol' : 'ul'
          return (
            <List
              key={key}
              className={`space-y-1 pl-5 ${block.ordered ? 'list-decimal' : 'list-disc'}`}
            >
              {block.items.map((item, itemIndex) => (
                // biome-ignore lint/suspicious/noArrayIndexKey: items never reorder
                <li key={itemIndex}>
                  <InlineParts parts={item} />
                </li>
              ))}
            </List>
          )
        })}
      </div>

      {(avoiding.length > 0 || restrictions.course) && (
        <div className="flex flex-wrap gap-1.5 text-xs">
          {avoiding.length > 0 && (
            <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200">
              {text.avoiding}: {avoiding.join(', ')}
            </span>
          )}
          {restrictions.course && (
            <span className="rounded-full bg-sky-50 px-2 py-0.5 text-sky-800 dark:bg-sky-950 dark:text-sky-200">
              {text.course}: {labels.courses[restrictions.course]}
            </span>
          )}
        </div>
      )}

      {response.notice && (
        <p
          role="note"
          className="rounded-lg border border-orange-200 bg-orange-50 px-3 py-2 text-sm text-orange-900 dark:border-orange-800 dark:bg-orange-950 dark:text-orange-100"
        >
          <strong>{text.notice}:</strong> {response.notice}
        </p>
      )}
    </div>
  )
}

function InlineParts({ parts }: { parts: Inline[] }) {
  // biome-ignore lint/suspicious/noArrayIndexKey: parts never reorder
  return parts.map((part, index) => <InlinePart key={index} part={part} />)
}

function InlinePart({ part }: { part: Inline }) {
  switch (part.type) {
    case 'text':
      return part.text
    case 'bold':
      return <strong>{part.text}</strong>
    case 'dish':
      // A dish named in the text gets a small marker; a bare citation shows the name.
      return part.named ? (
        <span title={part.name} className="text-red-700" aria-hidden="true">
          {' '}
          ●
        </span>
      ) : (
        <span className="rounded-md bg-red-100 px-1.5 py-0.5 font-medium text-red-900 dark:bg-red-900 dark:text-red-100">
          {part.name}
        </span>
      )
  }
}
