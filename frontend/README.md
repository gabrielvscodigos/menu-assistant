# menu-assistant front end

A chat interface for menu-assistant, where a mascot talks with the guest. It calls the
FastAPI backend (`POST /ask`) and keeps the conversation in the browser, since the API is
stateless.

> Work in progress: this is the project skeleton. The chat and the mascot come next.

## Stack

| Concern          | Choice                                        |
| ---------------- | --------------------------------------------- |
| Language         | TypeScript (strict)                           |
| UI               | React 19 + Vite                               |
| Styling          | Tailwind CSS 4                                |
| Mascot animation | SVG + Motion (planned)                        |
| Tests            | Vitest + Testing Library (jsdom)              |
| Lint and format  | Biome                                         |
| Package manager  | pnpm                                          |

Why these: see [decision 024](../docs/decisions.md#024--front-end-react-vite-typescript-tailwind-biome).

## Requirements

- Node.js 22.13 or newer
- pnpm 10 (`npm install -g pnpm`)

## Commands

Run them inside `frontend/`:

| Task              | Command          |
| ----------------- | ---------------- |
| Install           | `pnpm install`   |
| Dev server        | `pnpm dev`       |
| Lint + format check | `pnpm lint`    |
| Fix lint + format | `pnpm format`    |
| Type check        | `pnpm typecheck` |
| Tests             | `pnpm test`      |
| Production build  | `pnpm build`     |

## Talking to the API

Start the API first (`uv run uvicorn menu_assistant.api.main:app --reload` from the
repository root). In development, Vite proxies `/api/*` to `http://127.0.0.1:8000`, so
the browser sees a single origin and the API needs no CORS settings. Set `API_URL` to
point the proxy elsewhere.
