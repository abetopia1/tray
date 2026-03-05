# CLAUDE.md — Tray Admin Dashboard

## Project Overview

Tray Admin is a full-stack admin back-office dashboard for a fintech payment platform. It provides operator tools for user management, KYC review, transaction oversight, merchant settlement, and customer support. Built with Next.js 14 (App Router), React 18, TypeScript, and Supabase (PostgreSQL + Auth + Edge Functions).

## Tech Stack

| Layer           | Technology                                      |
|-----------------|------------------------------------------------|
| Framework       | Next.js 14 (App Router)                        |
| Language        | TypeScript 5.5 (strict mode)                   |
| UI              | React 18, inline CSS (no CSS framework)        |
| Backend/DB      | Supabase (PostgreSQL with RLS)                 |
| Auth            | Supabase Auth (email/password, cookie-based)   |
| Edge Functions  | Supabase Edge Functions (Deno runtime)         |
| i18n            | Custom context-based (Arabic RTL + English)    |

## Commands

```bash
npm run dev       # Start dev server (localhost:3000)
npm run build     # Production build (also validates TypeScript)
npm start         # Run production server
npm run lint      # ESLint via next lint
```

There is no test framework configured. No Makefile or CI/CD pipeline exists.

## Project Structure

```
src/
├── app/                           # Next.js App Router
│   ├── layout.tsx                 # Root layout (html/body, metadata)
│   ├── page.tsx                   # / → redirects to /admin
│   ├── login/page.tsx             # Login page
│   ├── unauthorized/page.tsx      # 403 page
│   └── admin/                     # Protected admin routes
│       ├── layout.tsx             # Admin shell with auth + i18n
│       ├── page.tsx               # Dashboard hub (KPIs, queues, search)
│       ├── context.tsx            # AdminContext (permissions, userId, roles)
│       ├── components/            # Shared admin components
│       ├── users/page.tsx         # User management
│       ├── transactions/page.tsx  # Transaction oversight
│       ├── kyc/page.tsx           # KYC review queue
│       ├── settlement/            # Settlement + reconciliation
│       └── support/page.tsx       # Support tickets
├── lib/
│   ├── audit.ts                   # writeAuditLog() helper
│   ├── permissions.ts             # RBAC: canAccessRoute(), canPerformAction()
│   ├── supabase/
│   │   ├── client.ts              # Browser Supabase client (anon key)
│   │   ├── server.ts              # Server Supabase client (cookies)
│   │   └── admin.ts               # Service-role Supabase client
│   └── i18n/
│       ├── context.tsx            # I18nProvider + useI18n hook
│       └── dictionaries.ts        # ar/en translation dictionaries
├── types/
│   └── database.ts                # TypeScript types for all DB tables
└── middleware.ts                   # Auth + role gate for /admin/*

supabase/
├── config.toml                    # Local Supabase config
├── migrations/                    # SQL migrations (schema + RLS + indexes)
└── functions/                     # Edge Functions (Deno)
    ├── admin-audit/               # Audit log writes
    ├── admin-kpis/                # Dashboard KPI computation
    ├── admin-search/              # Global user/transaction search
    ├── admin-settlement-generate/ # Settlement batch creation
    ├── admin-balance-adjust/      # Manual balance adjustments (admin-only)
    ├── admin-reconcile-upload/    # Reconciliation file upload
    └── _shared/cors.ts            # CORS headers helper
```

## Architecture & Key Patterns

### Authentication & Authorization

- **Middleware** (`src/middleware.ts`): Intercepts all `/admin/*` routes. Redirects unauthenticated users to `/login`, unauthorized users to `/unauthorized`.
- **4 admin roles**: `admin`, `compliance`, `finance`, `support`
- **RBAC** (`src/lib/permissions.ts`): `ROUTE_ACCESS` controls page visibility per role; `ACTION_PERMISSIONS` gates individual operations. `admin` role has access to everything.
- **Supabase clients**: Use `client.ts` for browser, `server.ts` for Server Components (reads cookies), `admin.ts` for service-role operations (never exposed to client).

### Component Patterns

- **Server Components** in layouts for auth checks and data fetching.
- **Client Components** (`'use client'`) for interactive UI.
- **Suspense boundaries** wrap components using `useSearchParams()` or async data.
- **AdminContext** (`src/app/admin/context.tsx`) provides `useAdmin()` hook with `userId`, `roles`, `permissions`.

### Internationalization

- Two locales: `ar` (Arabic, RTL, default) and `en` (English, LTR).
- Custom `I18nProvider` + `useI18n()` hook in `src/lib/i18n/`.
- Translation keys in `src/lib/i18n/dictionaries.ts`.
- Dynamic `dir` attribute on root HTML element for RTL support.

### Database

- PostgreSQL via Supabase with Row Level Security (RLS) on all tables.
- Core tables: `profiles`, `user_roles`, `merchants`, `transactions`, `kyc_reviews`, `settlement_batches`, `reconciliation_exceptions`, `support_tickets`, `audit_logs`, `devices`, `app_config`.
- Types defined in `src/types/database.ts`.
- Migrations in `supabase/migrations/`.

### Edge Functions

- All Edge Functions run on Deno runtime under `supabase/functions/`.
- Auth-gated: each function verifies the caller's JWT and admin role.
- Service-role writes ensure audit logs and privileged operations bypass RLS safely.

### Audit Logging

- Append-only `audit_logs` table.
- `writeAuditLog()` in `src/lib/audit.ts` calls the `admin-audit` Edge Function.
- Captures: `actor_id`, `action`, `resource_type`, `resource_id`, `metadata`, `ip_address`.

## Coding Conventions

- **TypeScript strict mode** — no `any` types, use interfaces from `src/types/database.ts`.
- **Path aliases** — use `@/*` to import from `src/*` (e.g., `@/lib/permissions`).
- **Inline CSS** — all styling uses React `style` props with `CSSProperties` objects. No external CSS framework.
- **camelCase** for variables and functions, **PascalCase** for components and types.
- **No test files** exist yet. Validate changes with `npm run build` and `npm run lint`.

## Environment Variables

Required in `.env.local` (see `.env.local.example`):

```
NEXT_PUBLIC_SUPABASE_URL=...       # Supabase project URL (public)
NEXT_PUBLIC_SUPABASE_ANON_KEY=...  # Supabase anon key (public)
SUPABASE_SERVICE_ROLE_KEY=...      # Service role key (server-only, NEVER expose to client)
```

## Security Notes

- Never expose `SUPABASE_SERVICE_ROLE_KEY` to client-side code.
- All database access uses RLS; service-role client is only used in Edge Functions and server-side code.
- `danger.*` actions (balance adjustments, force logout, audit viewing) are restricted to the `admin` role only.
- PIN confirmation is required for balance adjustments via the `admin-balance-adjust` Edge Function.
