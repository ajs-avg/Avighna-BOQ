# Avighna BOQ — Web (frontend)

"Drop a drawing, get a measurement sheet."

This is the review / approval cockpit for the Avighna BOQ platform. Users upload construction
drawings (DWG / DXF / PDF / PNG / JPG / TIFF); the FastAPI backend converts and interprets them and
produces an Excel measurement sheet. Two modules:

- **Structural — Reinforcement BBS**: RCC drawings → bar bending schedule (tons).
- **Interior Fit-out — BOQ**: interior design drawings → bill of quantities (m² / lm / nos).

Engineers watch the pipeline, check and correct the extracted members / items, reviewers approve,
and anyone downloads the Excel.

## Stack

- Next.js 15.5 (App Router), React 19, TypeScript 5 (strict)
- Tailwind CSS v4 (`app/globals.css` → `@import "tailwindcss"` + `@theme` brand tokens)
- Local accounts: JWT from `POST /api/v1/auth/login` kept in `localStorage` + an `avighna_token`
  cookie for the route guard in `middleware.ts`. No Supabase.
- `lucide-react` icons, `clsx` + `tailwind-merge`. Every component is hand-written in `components/`.

## Run locally

```bash
cd frontend
cp .env.example .env.local        # NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev                       # http://localhost:3000
```

The backend must be running at `NEXT_PUBLIC_API_URL` (see `docs/API_CONTRACT.md`). Sign in with an
account created by an admin; invited users set their own password on first sign-in.

Other scripts:

```bash
npm run build       # production build (type-check + lint included)
npm run start       # serve the production build
npm run lint        # eslint (next/core-web-vitals + next/typescript)
npm run typecheck   # tsc --noEmit
```

## Environment variables

| Variable | Purpose |
| --- | --- |
| `NEXT_PUBLIC_API_URL` | Base URL of the FastAPI backend, e.g. `http://localhost:8000` locally or the Render URL in production (no trailing slash) |

## Project layout

```
app/
  layout.tsx               root html/body, Inter font, Toast + Confirm providers
  globals.css              Tailwind v4 + brand tokens + table/field utilities
  (auth)/                  login, set-password (split brand panel + card)
  (app)/                   authenticated shell (sidebar + header + user context)
    page.tsx               dashboard
    new/page.tsx           new measurement (module → drawings → details → standards)
    jobs/page.tsx          jobs list (filters, pagination, delete)
    jobs/[id]/page.tsx     job detail (summary / members / BOQ / rooms / sheets)
    standards/page.tsx     company BBS standards (admin edits)
    users/page.tsx         user management (admin)
components/
  ui/                      Button, Card, Input, Select, Badge, StatusPill, ProgressBar, Tabs,
                           Table, Dialog, ConfirmDialog, Toast, Menu, Switch, Alert, Skeleton…
  structural/              SummaryTable, BarRowsTable, MemberTab, MemberEditor, editors
  fitout/                  BOQSummaryCards, BOQTab, ItemEditor, RoomsTable
  AppShell, Dropzone, Timeline, SheetsTab, StandardsForm, JobDetail, …
lib/
  api.ts                   single fetch layer for the FastAPI backend (bearer, errors, XHR upload)
  auth.ts                  token / profile / cookie storage
  types.ts                 mirrors docs/API_CONTRACT.md
  format.ts                number / date / unit / bar-group formatting
  constants.ts             status, module, role and basis metadata
  user-context.tsx         useUser() — profile + role helpers
middleware.ts              redirects unauthenticated visitors to /login
```

## Roles

- `engineer` — upload, review and edit members / items.
- `reviewer` — everything above plus **Approve**.
- `admin` — everything above plus Standards editing and the Users page.

## Deploy on Vercel

1. Import the repository, set **Root Directory** to `frontend`.
2. Framework preset: Next.js (auto-detected). Node.js 20+.
3. Add `NEXT_PUBLIC_API_URL` for Production and Preview.
4. Deploy. Make sure the backend's CORS allow-list includes the Vercel domain.
