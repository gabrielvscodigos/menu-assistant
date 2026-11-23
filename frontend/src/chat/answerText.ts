// Turns the assistant's reply into blocks the UI can render. The LLM writes light markdown
// (paragraphs, "- " / "1. " lists, **bold**) and cites dishes as [dish-id]. Only those
// pieces are understood; everything else stays plain text, and React escapes it all.
import type { DishSource } from '../api/client'

export type Inline =
  | { type: 'text'; text: string }
  | { type: 'bold'; text: string }
  // `named`: the dish name is written right before the citation, so only a marker is needed.
  | { type: 'dish'; id: string; name: string; named: boolean }

export type Block =
  | { type: 'paragraph'; lines: Inline[][] }
  | { type: 'list'; ordered: boolean; items: Inline[][] }

const LIST_ITEM = /^\s*(?:[-*•]|(\d+)[.)])\s+(.*)$/
const INLINE = /\*\*(.+?)\*\*|\[([a-z0-9]+(?:-[a-z0-9]+)*)\]/g

export function parseAnswer(text: string, dishes: readonly DishSource[]): Block[] {
  const names = new Map(dishes.map((dish) => [dish.id, dish.name]))
  const blocks: Block[] = []

  for (const line of text.split('\n')) {
    const last = blocks.at(-1)
    if (!line.trim()) {
      blocks.push({ type: 'paragraph', lines: [] }) // a blank line ends the block
      continue
    }
    const item = LIST_ITEM.exec(line)
    if (item) {
      const ordered = item[1] !== undefined
      const inline = parseInline(item[2], names)
      if (last?.type === 'list' && last.ordered === ordered) {
        last.items.push(inline)
      } else {
        blocks.push({ type: 'list', ordered, items: [inline] })
      }
    } else if (last?.type === 'paragraph') {
      last.lines.push(parseInline(line.trim(), names))
    } else {
      blocks.push({ type: 'paragraph', lines: [parseInline(line.trim(), names)] })
    }
  }
  return blocks.filter((block) => block.type === 'list' || block.lines.length > 0)
}

export function parseInline(line: string, names: ReadonlyMap<string, string>): Inline[] {
  const parts: Inline[] = []
  let end = 0
  for (const match of line.matchAll(INLINE)) {
    if (match.index > end) {
      parts.push({ type: 'text', text: line.slice(end, match.index) })
    }
    const [whole, bold, id] = match
    const name = id ? names.get(id) : undefined
    if (bold !== undefined) {
      parts.push({ type: 'bold', text: bold })
    } else if (id && name) {
      parts.push({ type: 'dish', id, name, named: endsWithName(parts, name) })
    } else {
      parts.push({ type: 'text', text: whole }) // a bracket that is not a known dish
    }
    end = match.index + whole.length
  }
  if (end < line.length) {
    parts.push({ type: 'text', text: line.slice(end) })
  }
  return markNamedAfter(parts)
}

// Small models also write the citation first: "[spicy-miso-ramen] Spicy Miso Ramen".
function markNamedAfter(parts: Inline[]): Inline[] {
  return parts.map((part, index) => {
    if (part.type !== 'dish' || part.named) {
      return part
    }
    const next = parts.slice(index + 1).find((p) => p.type === 'dish' || p.text.trim() !== '')
    const named =
      next !== undefined &&
      next.type !== 'dish' &&
      next.text.trimStart().toLowerCase().startsWith(part.name.toLowerCase())
    return named ? { ...part, named } : part
  })
}

// True if the text right before (ignoring spaces) ends with the dish name.
function endsWithName(parts: readonly Inline[], name: string): boolean {
  const previous = parts.findLast((part) => part.type === 'dish' || part.text.trim() !== '')
  if (!previous || previous.type === 'dish') {
    return false
  }
  return previous.text.trimEnd().toLowerCase().endsWith(name.toLowerCase())
}
