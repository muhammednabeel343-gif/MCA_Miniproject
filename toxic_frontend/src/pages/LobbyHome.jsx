import { Link } from "react-router-dom";
import { getUser } from "../utils/auth";

const features = [
  {
    title: "Real-Time Safety",
    text: "Toxic messages are detected while you play.",
    icon: "◈",
  },
  {
    title: "Multiplayer Rooms",
    text: "Create rooms or join other active players.",
    icon: "⌁",
  },
  {
    title: "Your Activity",
    text: "Track messages, toxicity levels, and warnings.",
    icon: "◌",
  },
];

export default function LobbyHome() {
  const user = getUser();
  const username = user?.username || "Player";

  return (
    <div className="app-page lobby-home-page">
      <div className="page-grid" aria-hidden="true" />
      <div className="page-content">
        <section className="welcome-panel">
          <div className="welcome-copy">
            <span className="eyebrow">TOXIC-SHIELD / PLAYER HUB</span>
            <h1>Welcome back, <span>{username}!</span></h1>
            <p>Choose a game, join a room, and play in a safer chat environment.</p>
            <div className="welcome-actions">
              <Link className="action-primary" to="/play-lobby">Play Now</Link>
              <Link className="action-secondary" to="/rooms">View Rooms</Link>
            </div>
          </div>
          <div className="welcome-signal" aria-hidden="true">
            <div className="signal-ring signal-ring-one" />
            <div className="signal-ring signal-ring-two" />
            <div className="signal-core">✓</div>
          </div>
        </section>

        <section className="feature-section">
          <div className="section-heading">
            <span className="eyebrow">THE SAFETY LAYER</span>
            <h2>How Toxic-Shield Works</h2>
          </div>
          <div className="feature-grid">
            {features.map((feature) => (
              <article className="feature-card" key={feature.title}>
                <span className="feature-icon">{feature.icon}</span>
                <h3>{feature.title}</h3>
                <p>{feature.text}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
