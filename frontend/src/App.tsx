import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./hooks/useSupabase";
import AuthGuard from "./components/AuthGuard";
import ErrorBoundary from "./components/ErrorBoundary";
import DigitizePage from "./pages/DigitizePage";
import BattlePage from "./pages/BattlePage";
import MemorialPage from "./pages/MemorialPage";
import LoginPage from "./pages/LoginPage";

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
                <AuthGuard>
                  <DigitizePage />
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
                  <MemorialPage />
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
