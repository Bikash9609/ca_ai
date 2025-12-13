import { Routes, Route } from "react-router-dom";
import Navigation from "./components/Navigation";
import {
  Dashboard,
  Clients,
  Documents,
  Chat,
  GSTFiling,
  Privacy,
} from "./pages";

function App() {
  return (
    <div className="min-h-screen bg-background flex">
      <Navigation />
      <main className="flex-1 ml-64">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/clients" element={<Clients />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/gst-filing" element={<GSTFiling />} />
          <Route path="/privacy" element={<Privacy />} />
        </Routes>
      </main>
    </div>
  );
}

export default App;
