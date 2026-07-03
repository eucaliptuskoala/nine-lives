import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./hooks/useSupabase";
import AuthGuard from "./components/AuthGuard";
import ErrorBoundary from "./components/ErrorBoundary";
import DigitizePage from "./pages/DigitizePage";
import BattlePage from "./pages/BattlePage";
import LoginPage from "./pages/LoginPage";
import HomePage from "./pages/HomePage";
import OverworldPage from "./pages/OverworldPage";

// The memorial is a secondary route reached only after a run ends, so we split
// it into its own chunk and load it on demand to keep the initial bundle lean.
const MemorialPage = lazy(() => import("./pages/MemorialPage"));

/** Retro-themed fallback shown while a lazily-loaded route chunk downloads. */
function RouteFallback() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-900 text-white">
      <p role="status" className="retro text-xs text-gray-400">
        Loading...
      </p>
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route
            path="/login"
            element={
              <ErrorBoundary>
                <LoginPage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/"
            element={
              <ErrorBoundary>
                <HomePage />
              </ErrorBoundary>
            }
          />
          <Route
            path="/digitize"
            element={
              <ErrorBoundary>
                <AuthGuard>
                  <DigitizePage />
                </AuthGuard>
              </ErrorBoundary>
            }
          />
          <Route
            path="/overworld"
            element={
              <ErrorBoundary>
                <AuthGuard>
                  <OverworldPage />
                </AuthGuard>
              </ErrorBoundary>
            }
          />
          <Route
            path="/battle/:runId"
            element={
              <ErrorBoundary>
                <AuthGuard>
                  <BattlePage />
                </AuthGuard>
              </ErrorBoundary>
            }
          />
          <Route
            path="/memorial"
            element={
              <ErrorBoundary>
                <AuthGuard>
                  <Suspense fallback={<RouteFallback />}>
                    <MemorialPage />
                  </Suspense>
                </AuthGuard>
              </ErrorBoundary>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
