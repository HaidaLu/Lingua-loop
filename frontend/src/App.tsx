import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import { api } from "./api";
import { useAuth } from "./auth";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Lookup from "./pages/Lookup";
import ReviewSession from "./pages/ReviewSession";
import CardList from "./pages/CardList";
import CardDetail from "./pages/CardDetail";
import AddCard from "./pages/AddCard";
import Decks from "./pages/Decks";
import ImportAnki from "./pages/ImportAnki";

export default function App() {
  const { ready, token, email, logout } = useAuth();
  const [provider, setProvider] = useState("");

  useEffect(() => {
    if (!token) return;
    api
      .health()
      .then((h) => setProvider(`${h.llm_provider}${h.llm_model ? ` · ${h.llm_model}` : ""}`))
      .catch(() => {});
  }, [token]);

  if (!ready) return <div className="app-loading">Loading…</div>;
  if (!token) return <Login />;

  return (
    <div className="app">
      <header>
        <div className="brand">
          Lingua Loop
          <span className="provider">LLM: {provider || "…"}</span>
        </div>
        <nav>
          <NavLink to="/" end>
            Dashboard
          </NavLink>
          <NavLink to="/review">Review</NavLink>
          <NavLink to="/lookup">Look up</NavLink>
          <NavLink to="/cards">Cards</NavLink>
          <NavLink to="/decks">Decks</NavLink>
          <button className="logout" title={email ?? ""} onClick={logout}>
            Sign out
          </button>
        </nav>
      </header>

      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/review" element={<ReviewSession />} />
        <Route path="/lookup" element={<Lookup />} />
        <Route path="/cards" element={<CardList />} />
        <Route path="/cards/new" element={<AddCard />} />
        <Route path="/cards/:id" element={<CardDetail />} />
        <Route path="/decks" element={<Decks />} />
        <Route path="/import/anki" element={<ImportAnki />} />
      </Routes>
    </div>
  );
}
