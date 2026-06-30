import { BrowserRouter, Routes, Route } from "react-router-dom";
import { AuthProvider } from "./hooks/useSupabase";
import AuthGuard from "./components/AuthGuard";
import DigitizePage from "./pages/DigitizePage";
import BattlePage from "./pages/BattlePage";
import MemorialPage from "./pages/MemorialPage";
import LoginPage from "./pages/LoginPage";

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            path="/"
            element={
              <AuthGuard>
                <DigitizePage />
              </AuthGuard>
            }
          />
          <Route
            path="/battle/:runId"
            element={
              <AuthGuard>
                <BattlePage />
              </AuthGuard>
            }
          />
          <Route
            path="/memorial"
            element={
              <AuthGuard>
                <MemorialPage />
              </AuthGuard>
            }
          />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
