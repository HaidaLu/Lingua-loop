import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";
import Heatmap from "../components/Heatmap";
import type { DeckOut, HeatmapResponse, ReviewStats } from "../types";

export default function Dashboard() {
  const { email } = useAuth();
  const [stats, setStats] = useState<ReviewStats | null>(null);
  const [heat, setHeat] = useState<HeatmapResponse | null>(null);
  const [decks, setDecks] = useState<DeckOut[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.stats().then(setStats).catch((e) => setErr(String(e)));
    api.heatmap(365).then(setHeat).catch(() => {});
    api.listDecks().then(setDecks).catch(() => {});
  }, []);

  const queueCount = stats
    ? stats.new_cards + stats.learn_now + stats.due_now
    : 0;

  return (
    <main className="page">
      <h1>Dashboard</h1>
      <p className="muted">{email}</p>
      {err && <div className="error">{err}</div>}

      <div className="stat-grid">
        <Stat label="New" value={stats?.new_cards} />
        <Stat label="Learn" value={stats?.learn_now} />
        <Stat label="Due" value={stats?.due_now} accent />
        <Stat label="Reviewed today" value={stats?.reviewed_today} />
      </div>
      {stats && (
        <p className="muted">
          {stats.total_cards} cards total · en {stats.by_language.en ?? 0} · de {stats.by_language.de ?? 0}
        </p>
      )}

      <div className="cta-row">
        <Link className="btn primary" to="/review">
          Start review{queueCount ? ` (${queueCount})` : ""}
        </Link>
        <Link className="btn" to="/lookup">
          Look up / new card
        </Link>
      </div>

      {heat && (
        <section className="hm-section">
          <div className="hm-head">
            <h2>Study activity</h2>
            <span className="muted">
              <b>{heat.current_streak}</b>-day streak · longest {heat.longest_streak} · {heat.active_days}{" "}
              active days / {heat.total_reviews} reviews
            </span>
          </div>
          <Heatmap days={heat.days} />
        </section>
      )}

      {decks.length > 0 && (
        <section>
          <div className="hm-head">
            <h2>Decks</h2>
            <Link className="muted" to="/decks">
              Manage →
            </Link>
          </div>
          <div className="deck-chips">
            {decks.map((d) => (
              <Link key={d.id} className="deck-chip" to={`/review?deck_id=${d.id}`}>
                {d.name}
                <span className="deck-chip-meta">
                  {d.card_count} cards
                  {(d.new_count || d.learn_count || d.due_count) > 0 && (
                    <>
                      {" · "}
                      {d.new_count > 0 && <span className="c-new">{d.new_count} new</span>}
                      {d.new_count > 0 && (d.learn_count > 0 || d.due_count > 0) && " · "}
                      {d.learn_count > 0 && <span className="c-learn">{d.learn_count} learn</span>}
                      {d.learn_count > 0 && d.due_count > 0 && " · "}
                      {d.due_count > 0 && <span className="c-due">{d.due_count} due</span>}
                    </>
                  )}
                </span>
              </Link>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}

function Stat({ label, value, accent }: { label: string; value?: number; accent?: boolean }) {
  return (
    <div className={`stat ${accent ? "accent" : ""}`}>
      <div className="stat-value">{value ?? "–"}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}
