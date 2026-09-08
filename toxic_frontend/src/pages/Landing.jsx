import { Link, useNavigate } from "react-router-dom";
import { getToken, getUser } from "../utils/auth";

export function ShieldMark() {
  return (
    <svg className="landing-shield" viewBox="0 0 48 56" aria-hidden="true">
      <defs>
        <linearGradient id="shield-gradient" x1="8" y1="4" x2="40" y2="52" gradientUnits="userSpaceOnUse">
          <stop stopColor="#60a5fa" />
          <stop offset="1" stopColor="#a855f7" />
        </linearGradient>
      </defs>
      <path d="M24 3 43 10v15c0 12.7-7.6 22.3-19 27C12.6 47.3 5 37.7 5 25V10L24 3Z" fill="rgba(168, 85, 247, 0.12)" stroke="url(#shield-gradient)" strokeWidth="2.5" />
      <path d="m15 27 6 6 12-14" fill="none" stroke="#bfdbfe" strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
    </svg>
  );
}

export default function Landing() {
  const navigate = useNavigate();
  const token = getToken();
  const user = getUser();

  const goPlay = () => {
    if (!token || !user) return navigate("/login");
    navigate("/lobby");
  };

  return (
    <div className="landing-page">
      <div className="landing-grid" aria-hidden="true" />
      <main className="landing-hero">
        <div className="landing-brand">
          <ShieldMark />
          <span>TOXIC-SHIELD</span>
        </div>

        <div className="landing-badge">MULTIPLAYER <span>•</span> REAL-TIME SAFETY</div>

        <h1>
          PLAY HARD.
          <span>CHAT SAFE.</span>
        </h1>

        <p className="landing-description">
          Join multiplayer arenas, compete with others, and experience real-time toxicity detection
          that keeps conversations fair and friendly.
        </p>

        <div className="landing-actions">
          <button className="landing-primary" onClick={goPlay}>Enter the Arena</button>
          <Link className="landing-secondary" to="/register">Create Account</Link>
        </div>
      </main>
    </div>
  );
}
