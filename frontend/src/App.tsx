import { BrowserRouter, Routes, Route } from "react-router-dom";
import DigitizePage from "./pages/DigitizePage";
import BattlePage from "./pages/BattlePage";
import MemorialPage from "./pages/MemorialPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<DigitizePage />} />
        <Route path="/battle/:runId" element={<BattlePage />} />
        <Route path="/memorial" element={<MemorialPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
