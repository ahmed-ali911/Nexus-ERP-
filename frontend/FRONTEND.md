# Sham ERP — Frontend

**Stack:** Vite 8 · React 19 · TypeScript 6 · MUI v9 · React Router v7 · TanStack Query v5 · react-hook-form + zod · i18next (AR/EN)

---

## Architecture Principles

### 1. Design Tokens (`src/theme/tokens.ts`)

Every visual value — color, radius, shadow, z-index — lives in `tokens.ts`. Components reference semantic names, not raw values.

```
tokens.ts ──► createAppTheme.ts ──► MUI theme ──► components
```

**To rebrand:** edit `tokens.ts` only. Zero component changes needed.

### 2. App Component Layer  ← THE MOST IMPORTANT RULE

**Screens NEVER import MUI directly.** They import only from `@/components/ui`.

```
screens  →  AppButton, AppCard, AppPage …  (our wrapper layer)
                        ↓
                  MUI internals             (implementation detail)
```

ESLint enforces this: `no-restricted-imports` warns on `@mui/*` inside `src/pages/**` and `src/routes/**`.

| Component | Purpose |
|-----------|---------|
| `AppButton` | variants: primary / secondary / text / danger + loading state |
| `AppInput` | standalone RTL-safe text field |
| `AppFormInput` | form-integrated (react-hook-form Controller) |
| `AppSelect` | labeled select with options array |
| `AppCard` | titled card with optional actions slot |
| `AppPage` | page wrapper: breadcrumbs + title + actions + content |
| `AppForm` | wraps FormProvider, renders `<form>`, integrates zod |
| `AppSpinner` | centered loading state |
| `AppDialog` | confirm/alert dialog with danger variant |

### 3. Theme Management (`src/theme/`)

```tsx
<AppThemeProvider>   // manages mode (light/dark) + direction
  <App />
</AppThemeProvider>

const { mode, direction, toggleMode } = useAppTheme();
```

Direction is **derived from language** — switching to Arabic sets `dir="rtl"` on `<html>` and swaps the Emotion RTL cache. No per-component CSS direction logic needed.

### 4. API Layer (`src/api/`)

```
hook → useHealth() → TanStack Query → apiClient (axios) → backend
```

- `apiClient`: base URL from `VITE_API_BASE_URL` (defaults to `""` → Vite proxy handles it in dev)
- JWT interceptor: attaches `Authorization: Bearer <token>` from localStorage
- 401 interceptor: refresh token flow → on failure, clear auth + redirect to `/login`
- Query hooks: one file per domain in `src/api/hooks/`

### 5. State Model

| State | Location | Examples |
|-------|----------|---------|
| Server data | TanStack Query | invoices, products, customers |
| Auth/session | `AuthContext` | user object, JWT token, permissions |
| Org scope | `OrgContext` | selected company / branch / warehouse |
| Notifications | `ToastContext` | `toast.success("Saved!")` |
| Local component | `useState` | form field, dialog open |

### 6. Routing (`src/routes/`)

- Lazy loading on all pages (`lazy(() => import("@/pages/…"))`) — automatic code splitting
- `ProtectedRoute` — redirects to `/login` when unauthenticated; DEV bypass lets you develop without login
- `<Can permission="module.resource.action">` — RBAC gate; renders children only when user has the permission string

### 7. Form Validation

Standard pattern for every form:

```tsx
const schema = z.object({ email: z.string().email() });
type FormData = z.infer<typeof schema>;

const methods = useForm<FormData>({ resolver: zodResolver(schema) });

return (
  <AppForm methods={methods} onSubmit={handleSubmit}>
    <AppFormInput name="email" label="Email" />
    <AppButton type="submit">Submit</AppButton>
  </AppForm>
);
```

### 8. i18n

- Default: **Arabic (AR)** → RTL direction
- Secondary: **English (EN)** → LTR direction
- Translations: `src/i18n/locales/{ar,en}/common.json`
- Language switch triggers direction switch automatically (no reload)

---

## Folder Structure

```
src/
├── api/              HTTP client + React Query hooks
│   ├── client.ts     axios instance, JWT interceptor, 401/refresh handler
│   ├── hooks/        one file per domain
│   └── index.ts
├── components/
│   └── ui/           App Component layer — the only place MUI is imported
├── contexts/         Auth, OrgScope, Toast
├── i18n/             i18next setup + locale files
├── pages/            Route-level screens (lazy loaded)
├── routes/           Router, ProtectedRoute, Can
├── theme/            tokens → MUI theme, ThemeProvider, useAppTheme
└── types/            Ambient declarations
```

## Commands

```bash
npm run dev      # Vite dev server :5174, proxies /api + /health → :8000
npm run build    # tsc + Vite build (clean = ship)
npm run lint     # ESLint — 0 errors required
npm run format   # Prettier
```

## Adding a New Screen

1. `src/pages/MyScreen.tsx` — import only from `@/components/ui`, `@/api`, `@/contexts`
2. `src/api/hooks/useMyResource.ts` — query/mutation hooks
3. Register in `src/routes/index.tsx` with `lazy(() => import("@/pages/MyScreen"))`
4. `<ProtectedRoute permission="module.resource.view">` if needed
5. Add translation keys to both locale files
