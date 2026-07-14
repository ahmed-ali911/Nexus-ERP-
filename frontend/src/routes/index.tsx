import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";
import { AppShell } from "@/components/layout";
import { AppSpinner } from "@/components/ui";

// ── Core pages ──────────────────────────────────────────────────────────────
const LoginPage      = lazy(() => import("@/pages/auth/LoginPage").then((m) => ({ default: m.LoginPage })));
const FoundationDemo = lazy(() => import("@/pages/FoundationDemo"));
const NotFound       = lazy(() => import("@/pages/NotFound"));
const DashboardPage  = lazy(() => import("@/pages/placeholder/DashboardPage").then((m) => ({ default: m.DashboardPage })));

// ── Sales ───────────────────────────────────────────────────────────────────
const SalesInvoicesPage  = lazy(() => import("@/pages/placeholder/sales").then((m) => ({ default: m.SalesInvoicesPage })));
const CollectionsPage    = lazy(() => import("@/pages/placeholder/sales").then((m) => ({ default: m.CollectionsPage })));
const CreditNotesPage    = lazy(() => import("@/pages/placeholder/sales").then((m) => ({ default: m.CreditNotesPage })));
const SalesCustomersPage = lazy(() => import("@/pages/placeholder/sales").then((m) => ({ default: m.SalesCustomersPage })));
const PriceListsPage     = lazy(() => import("@/pages/placeholder/sales").then((m) => ({ default: m.PriceListsPage })));

// ── Purchasing ──────────────────────────────────────────────────────────────
const PurchaseOrdersPage    = lazy(() => import("@/pages/placeholder/purchasing").then((m) => ({ default: m.PurchaseOrdersPage })));
const GoodsReceiptsPage     = lazy(() => import("@/pages/placeholder/purchasing").then((m) => ({ default: m.GoodsReceiptsPage })));
const SupplierInvoicesPage  = lazy(() => import("@/pages/placeholder/purchasing").then((m) => ({ default: m.SupplierInvoicesPage })));
const PurchasingPaymentsPage = lazy(() => import("@/pages/placeholder/purchasing").then((m) => ({ default: m.PurchasingPaymentsPage })));
const SuppliersPage         = lazy(() => import("@/pages/placeholder/purchasing").then((m) => ({ default: m.SuppliersPage })));

// ── Inventory ───────────────────────────────────────────────────────────────
const InventoryProductsPage = lazy(() => import("@/pages/placeholder/inventory").then((m) => ({ default: m.InventoryProductsPage })));
const StockBalancesPage     = lazy(() => import("@/pages/placeholder/inventory").then((m) => ({ default: m.StockBalancesPage })));
const MovementsPage         = lazy(() => import("@/pages/placeholder/inventory").then((m) => ({ default: m.MovementsPage })));
const TransfersPage         = lazy(() => import("@/pages/placeholder/inventory").then((m) => ({ default: m.TransfersPage })));
const BatchesPage           = lazy(() => import("@/pages/placeholder/inventory").then((m) => ({ default: m.BatchesPage })));

// ── Accounting ──────────────────────────────────────────────────────────────
const ChartOfAccountsPage = lazy(() => import("@/pages/placeholder/accounting").then((m) => ({ default: m.ChartOfAccountsPage })));
const JournalEntriesPage  = lazy(() => import("@/pages/placeholder/accounting").then((m) => ({ default: m.JournalEntriesPage })));
const TrialBalancePage    = lazy(() => import("@/pages/placeholder/accounting").then((m) => ({ default: m.TrialBalancePage })));
const ProfitLossPage      = lazy(() => import("@/pages/placeholder/accounting").then((m) => ({ default: m.ProfitLossPage })));
const BalanceSheetPage    = lazy(() => import("@/pages/placeholder/accounting").then((m) => ({ default: m.BalanceSheetPage })));

// ── System ──────────────────────────────────────────────────────────────────
const UsersRolesPage     = lazy(() => import("@/pages/placeholder/system").then((m) => ({ default: m.UsersRolesPage })));
const OrganizationPage   = lazy(() => import("@/pages/placeholder/system").then((m) => ({ default: m.OrganizationPage })));
const ApprovalsPage      = lazy(() => import("@/pages/placeholder/system").then((m) => ({ default: m.ApprovalsPage })));
const SystemSettingsPage = lazy(() => import("@/pages/placeholder/system").then((m) => ({ default: m.SystemSettingsPage })));

function PageLoader() {
  return <AppSpinner fullPage />;
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Public */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/403"   element={<div>Access Denied</div>} />

          {/* Protected — all nested under AppShell */}
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="demo"      element={<FoundationDemo />} />

            {/* Sales */}
            <Route path="sales">
              <Route path="invoices"     element={<SalesInvoicesPage />} />
              <Route path="collections"  element={<CollectionsPage />} />
              <Route path="credit-notes" element={<CreditNotesPage />} />
              <Route path="customers"    element={<SalesCustomersPage />} />
              <Route path="price-lists"  element={<PriceListsPage />} />
            </Route>

            {/* Purchasing */}
            <Route path="purchasing">
              <Route path="orders"    element={<PurchaseOrdersPage />} />
              <Route path="receipts"  element={<GoodsReceiptsPage />} />
              <Route path="invoices"  element={<SupplierInvoicesPage />} />
              <Route path="payments"  element={<PurchasingPaymentsPage />} />
              <Route path="suppliers" element={<SuppliersPage />} />
            </Route>

            {/* Inventory */}
            <Route path="inventory">
              <Route path="products"  element={<InventoryProductsPage />} />
              <Route path="balances"  element={<StockBalancesPage />} />
              <Route path="movements" element={<MovementsPage />} />
              <Route path="transfers" element={<TransfersPage />} />
              <Route path="batches"   element={<BatchesPage />} />
            </Route>

            {/* Accounting */}
            <Route path="accounting">
              <Route path="accounts"      element={<ChartOfAccountsPage />} />
              <Route path="journal"       element={<JournalEntriesPage />} />
              <Route path="trial-balance" element={<TrialBalancePage />} />
              <Route path="pnl"           element={<ProfitLossPage />} />
              <Route path="balance-sheet" element={<BalanceSheetPage />} />
            </Route>

            {/* System */}
            <Route path="system">
              <Route path="users"        element={<UsersRolesPage />} />
              <Route path="organization" element={<OrganizationPage />} />
              <Route path="approvals"    element={<ApprovalsPage />} />
              <Route path="settings"     element={<SystemSettingsPage />} />
            </Route>
          </Route>

          {/* Root redirect */}
          <Route path="/"  element={<Navigate to="/app" replace />} />
          <Route path="*"  element={<NotFound />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
