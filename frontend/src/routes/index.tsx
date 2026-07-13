import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";
import { AppShell } from "@/components/layout";
import { AppSpinner } from "@/components/ui";

// Lazy-loaded pages
const LoginPage     = lazy(() => import("@/pages/auth/LoginPage").then((m) => ({ default: m.LoginPage })));
const FoundationDemo  = lazy(() => import("@/pages/FoundationDemo"));
const NotFound        = lazy(() => import("@/pages/NotFound"));
const DashboardPage   = lazy(() => import("@/pages/placeholder/DashboardPage").then((m) => ({ default: m.DashboardPage })));
const ProductsPage    = lazy(() => import("@/pages/placeholder/ProductsPage").then((m) => ({ default: m.ProductsPage })));
const InventoryPage   = lazy(() => import("@/pages/placeholder/InventoryPage").then((m) => ({ default: m.InventoryPage })));
const InvoicesPage    = lazy(() => import("@/pages/placeholder/InvoicesPage").then((m) => ({ default: m.InvoicesPage })));
const AccountingPage  = lazy(() => import("@/pages/placeholder/AccountingPage").then((m) => ({ default: m.AccountingPage })));
const PurchasingPage  = lazy(() => import("@/pages/placeholder/PurchasingPage").then((m) => ({ default: m.PurchasingPage })));
const SettingsPage    = lazy(() => import("@/pages/placeholder/SettingsPage").then((m) => ({ default: m.SettingsPage })));

function PageLoader() {
  return <AppSpinner fullPage />;
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Public — login redirects to /app/dashboard if already authenticated */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/403"   element={<div>Access Denied</div>} />

          {/* Protected routes — all nested under AppShell layout */}
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <AppShell />
              </ProtectedRoute>
            }
          >
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard"  element={<DashboardPage />} />
            <Route path="products"   element={<ProductsPage />} />
            <Route path="inventory"  element={<InventoryPage />} />
            <Route path="invoices"   element={<InvoicesPage />} />
            <Route path="accounting" element={<AccountingPage />} />
            <Route path="purchasing" element={<PurchasingPage />} />
            <Route path="settings"   element={<SettingsPage />} />
            <Route path="demo"       element={<FoundationDemo />} />
          </Route>

          {/* Default */}
          <Route path="/"  element={<Navigate to="/app" replace />} />
          <Route path="*"  element={<NotFound />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
