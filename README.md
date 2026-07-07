# Nexus ERP

A deployable, production-grade ERP system for food manufacturing and distribution companies in the Gulf region. Built as a single codebase deployed per-client via Docker (not multi-tenant SaaS), with configuration-driven customization so the same code serves many companies without forking.

Developed against a real reference case — a Kuwaiti nut & coffee milling and distribution business (multiple retail branches plus a production mill) — to ground every module in genuine operational requirements.

**Stack:** FastAPI · PostgreSQL · SQLAlchemy · Alembic · React + TypeScript · Docker

---

## Status

**Backend: complete and fully tested — 203 passing tests across 9 modules.**
Frontend: foundation scaffold (bilingual AR/EN with RTL/LTR); business screens in progress.

Every module was designed, reviewed, built, tested, and committed independently. No module was merged until its full test suite passed, and every database migration is verified to run cleanly from an empty database — the real client-deployment path.

---

## Architecture principles

These rules hold across the whole system:

- **Deployable product, not SaaS.** One codebase, one Docker deployment per client. Differences between clients are driven by configuration and feature flags, never by forking the code.
- **Organizational hierarchy:** `Company → Branch → Warehouse`. A single deployment can hold one or more Companies (legal entities), so a client can be a single company with branches or a holding group.
- **Immutable financial ledgers.** Stock movements and journal entries are append-only. "Editing" means posting a reversing or adjustment entry — never mutating or deleting a posted record. This gives a complete, tamper-evident audit trail.
- **No stored balances.** Inventory balances and account balances are always derived from their immutable ledgers, so reported figures can never silently drift from the underlying records.
- **Exact arithmetic.** All money and quantity math uses `NUMERIC` (never floating point), aligned to the Kuwaiti Dinar's 3-decimal precision.
- **Configurable posting.** Business modules never write journal entries directly — they emit events, and an isolated Posting Engine translates them into balanced entries using database-driven, versioned templates. Accounting policy changes by editing a template, not the code.
- **Unified approvals & exceptions.** A single approval framework (maker/checker) governs every exceptional operation — credit-limit overrides, negative stock, discount overrides, cancellations, period reopening — through one consistent cycle: validate → detect exception → request approval → approve/reject → execute → audit → notify.
- **Advanced RBAC.** Dynamic, per-company roles: permissions are system-defined, but each company composes its own roles, all scoped to the organizational hierarchy.

---

## Modules

| # | Module | Highlights |
|---|--------|-----------|
| 1 | **Organization** | Company / Branch / Warehouse hierarchy; reversible cascade soft-delete; scoped uniqueness |
| 2 | **Auth & RBAC** | JWT auth, refresh-token revocation, account lockout; dynamic per-company roles & permissions; audit trail |
| 3 | **Master Data** | Products, categories, customers, suppliers; multi-unit of measure with exact weight/count conversions |
| 4 | **Inventory** | Immutable stock ledger; weighted-average costing; batch/expiry tracking (FEFO); inter-warehouse transfers; guarded negative stock |
| 5 | **Sales** | Invoices, credit notes, collections (FIFO + manual allocation); price lists; dynamic credit exposure; full lifecycle |
| 6 | **Purchasing** | Purchase orders, goods receipts, supplier invoices, returns, payments; three-way-match ready; GRN accrual accounting |
| 7 | **Accounting** | Isolated Posting Engine; DB-driven posting templates; hierarchical chart of accounts; fiscal periods; GL, Trial Balance, P&L, Balance Sheet (with computed retained earnings) |
| 8 | **Financial Integration** | Auto-posting from sales/purchasing/inventory via an EventPublisher; atomic journal + stock; COGS at exact issued cost |
| — | **Shared** | Cross-module approval framework (single source of truth) |

---

## Financial correctness

The system's accuracy is proven, not asserted:

- **The Balance Sheet balances** on seeded data: assets = liabilities + equity, including dynamically computed retained earnings — with no year-end closing run required.
- **Accounting inventory reconciles exactly with physical inventory** — the GL inventory account equals the stock-ledger value to zero difference after a full sequence of operations. This is enforced by an automated reconciliation test.
- **The Posting Engine is provably isolated** — an AST-based contract test verifies it imports nothing from any business module, so future modules (payroll, manufacturing, POS) integrate by emitting events with zero engine changes.

---

## Project structure

```
nexus-erp/
├── backend/            FastAPI application
│   └── app/
│       ├── core/       config, database, RBAC, audit, shared mixins
│       └── modules/    organization, auth, master_data, inventory,
│                       sales, purchasing, accounting, shared
├── database/
│   ├── migrations/     Alembic migrations (verified from empty DB)
│   └── seed/           reference dataset + default catalogs
├── frontend/           React + TypeScript (Vite), bilingual AR/EN
├── deploy/             on-prem and hosted deployment notes
└── docker-compose.yml
```

---

## Running locally

```bash
cp .env.example .env
docker-compose up --build          # backend + postgres + redis
curl http://localhost:8000/health  # {"status":"ok"}
```

Interactive API docs (Swagger) are available at `http://localhost:8000/docs`.

```bash
cd frontend && npm install && npm run dev
```

---

## Testing

```bash
docker-compose exec backend uv run pytest
```

The full suite (203 tests) covers business rules, financial correctness, edge cases, isolation contracts, and cross-module regression. Migrations are separately verified to apply cleanly from an empty database.

---

*Private repository. All rights reserved.*

