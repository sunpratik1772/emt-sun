/**
 * Vite entry point + top-level routing.
 */
import React, { Suspense, lazy } from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
} from 'react-router-dom'

import App from './App.tsx'
import LoginPage from './pages/LoginPage'
import AuthCallback from './pages/AuthCallback'
import ProtectedRoute from './components/ProtectedRoute'
import ErrorBoundary from './components/ErrorBoundary'
import { useApplyTheme } from './store/themeStore'
import './styles/linear-tokens.css'
import './styles/globals.css'
import './styles/dashboard.css'
import './styles/docs.css'
import './styles/studio-overlay.css'
import './styles/agent-animations.css'
import './styles/sherpa-clarification.css'

const DocsPage = lazy(() => import('./pages/docs/DocsPage'))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

function ThemeRoot({ children }: { children: React.ReactNode }) {
  useApplyTheme()
  return <>{children}</>
}

function AppRouter() {
  const location = useLocation()
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />
  }
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/docs/*"
        element={
          <Suspense fallback={<div className="p-8 text-[var(--text-2)]">Loading docs…</div>}>
            <DocsPage />
          </Suspense>
        }
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <App />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <ErrorBoundary region="Application">
          <ThemeRoot>
            <AppRouter />
          </ThemeRoot>
        </ErrorBoundary>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
)
