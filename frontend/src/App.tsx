import "./i18n";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppThemeProvider } from "@/theme";
import { AuthProvider } from "@/contexts/AuthContext";
import { OrgProvider } from "@/contexts/OrgContext";
import { ToastProvider } from "@/contexts/ToastContext";
import { AppRouter } from "@/routes";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <AppThemeProvider>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <AuthProvider>
            <OrgProvider>
              <AppRouter />
            </OrgProvider>
          </AuthProvider>
        </ToastProvider>
      </QueryClientProvider>
    </AppThemeProvider>
  );
}
