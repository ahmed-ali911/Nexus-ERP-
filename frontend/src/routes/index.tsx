import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./ProtectedRoute";
import { AppSpinner } from "@/components/ui";

// Lazy-loaded pages (code-splitting pattern for all future screens)
const FoundationDemo = lazy(() => import("@/pages/FoundationDemo"));
const NotFound = lazy(() => import("@/pages/NotFound"));

function PageLoader() {
  return <AppSpinner fullPage />;
}

export function AppRouter() {
  return (
    <BrowserRouter>
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<div>Login — coming soon</div>} />
          <Route path="/403" element={<div>Access Denied</div>} />

          {/* Protected routes */}
          <Route
            path="/app"
            element={
              <ProtectedRoute>
                <FoundationDemo />
              </ProtectedRoute>
            }
          />

          {/* Default */}
          <Route path="/" element={<Navigate to="/app" replace />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}
