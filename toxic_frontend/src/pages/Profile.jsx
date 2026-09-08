import { useState, useEffect } from "react";
import { API_BASE_URL } from "../config";
import { authHeaders } from "../utils/auth";

export default function Profile() {
  const [stats, setStats] = useState(null);
  const [activityGame, setActivityGame] = useState("");
  const [activityDate, setActivityDate] = useState("");
  const [referenceTime] = useState(() => Date.now());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStats();
  }, []);

  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/users/me/stats`, {
        headers: authHeaders(),
      });

      if (!response.ok) throw new Error("Could not load stats.");

      const data = await response.json();
      setStats(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.loading}>
        <span className="counter">Loading profile dashboard...</span>
      </div>
    );
  }

  if (error) {
    return <div style={styles.error}>{error}</div>;
  }

  const toxicityRate = stats.toxicity_percentage;
  const radius = 50;
  const circumference = 2 * Math.PI * radius;
  const strokeOffset =
    circumference - (toxicityRate / 100) * circumference;
  const activityGames = [...new Set(stats.recent_messages.map((message) => message.game_name || "Lobby"))];
  const filteredActivities = stats.recent_messages.filter((message) => {
    const matchesGame = !activityGame || (message.game_name || "Lobby") === activityGame;
    const age = referenceTime - new Date(message.created_at).getTime();
    const matchesDate = !activityDate ||
      (activityDate === "today" && age < 86400000) ||
      (activityDate === "7" && age < 604800000) ||
      (activityDate === "30" && age < 2592000000);
    return matchesGame && matchesDate;
  });

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>Your Gaming Profile</h1>
        <p style={styles.subtitle}>
          Track your overall chat activity, safety rating, warnings, and recent activity.
        </p>
      </header>

      <div style={styles.statsGrid}>
        <div className="card" style={styles.statCard}>
          <span style={styles.statVal}>{stats.total_messages}</span>
          <span style={styles.statLabel}>Total Chats Sent</span>
        </div>
        <div className="card" style={styles.statCard}>
          <span style={{ ...styles.statVal, color: "var(--status-safe)" }}>{stats.safe_messages}</span>
          <span style={styles.statLabel}>Safe Messages</span>
        </div>
        <div className="card" style={styles.statCard}>
          <span style={{ ...styles.statVal, color: "var(--status-toxic)" }}>{stats.toxic_messages}</span>
          <span style={styles.statLabel}>Toxic Messages</span>
        </div>
        <div className="card" style={styles.statCard}>
          <span style={{ ...styles.statVal, color: "var(--status-warn)" }}>{stats.warning_count}</span>
          <span style={styles.statLabel}>Warnings Received</span>
        </div>
      </div>

      <div style={styles.detailGrid}>
        <div className="card glass" style={styles.chartCard}>
          <h3 style={styles.cardTitle}>Toxicity Index</h3>
          <div style={styles.chartWrapper}>
            <svg width="150" height="150" viewBox="0 0 120 120">
              <circle cx="60" cy="60" r={radius} fill="transparent" stroke="var(--border)" strokeWidth="10" />
              <circle cx="60" cy="60" r={radius} fill="transparent" stroke={toxicityRate > 20 ? "var(--status-toxic)" : "var(--status-safe)"} strokeWidth="10" strokeDasharray={circumference} strokeDashoffset={strokeOffset} strokeLinecap="round" transform="rotate(-90 60 60)" />
              <text x="60" y="65" textAnchor="middle" fill="var(--text-h)" fontSize="18" fontWeight="700">{toxicityRate}%</text>
            </svg>
          </div>
          <p style={styles.chartExplain}>
            {toxicityRate > 25
              ? "Warning: Your toxicity rate is above average. Please maintain friendly game conversations."
              : "Excellent! Your account maintains a safe gaming rating."}
          </p>
          <div style={styles.statusBox}>
            <span style={styles.statusLabelSmall}>Account Status:</span>
            <span className={`badge ${stats.status === "ACTIVE" ? "badge-safe" : stats.status === "RESTRICTED" ? "badge-warn" : "badge-toxic"}`}>{stats.status}</span>
          </div>
        </div>

        <div className="card glass recentCard" style={styles.recentCard}>
          <h3 style={styles.cardTitle}>Recent Room Activities</h3>
          <div className="activity-filters">
            <label>Game<select value={activityGame} onChange={(event) => setActivityGame(event.target.value)}><option value="">All Games</option>{activityGames.map((game) => <option key={game} value={game}>{game}</option>)}</select></label>
            <label>Date<select value={activityDate} onChange={(event) => setActivityDate(event.target.value)}><option value="">All Dates</option><option value="today">Today</option><option value="7">Last 7 Days</option><option value="30">Last 30 Days</option></select></label>
          </div>
          {filteredActivities.length === 0 ? (
            <p style={styles.emptyText}>No recent chat logs found.</p>
          ) : (
            <div className="record-scroll activity-list" style={styles.msgList}>
              {filteredActivities.map((message, index) => (
                <div key={index} style={styles.msgItem}>
                  <div style={styles.msgItemHeader}>
                    <span style={styles.msgGame}>{message.game_name || "Lobby"}</span>
                    <span className={`badge ${message.status === "Safe" ? "badge-safe" : "badge-toxic"}`} style={{ fontSize: "10px" }}>{message.prediction}</span>
                  </div>
                  <p style={styles.msgBody}>&quot;{message.message}&quot;</p>
                  <span style={styles.msgDate}>{new Date(message.created_at).toLocaleString()}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const styles = {
  container: { padding: "20px 0" },
  header: { marginBottom: "30px" },
  title: { fontSize: "28px", fontWeight: "700", color: "var(--text-h)", margin: "0 0 6px 0" },
  subtitle: { color: "var(--text)", fontSize: "14px", margin: 0 },
  statsGrid: { display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "20px", marginBottom: "30px" },
  statCard: { display: "flex", flexDirection: "column", alignItems: "center", padding: "20px" },
  statVal: { fontSize: "36px", fontWeight: "800", color: "var(--text-h)", marginBottom: "4px" },
  statLabel: { fontSize: "13px", color: "var(--text)", fontWeight: "600" },
  detailGrid: { display: "grid", gridTemplateColumns: "1fr 2fr", gap: "30px" },
  chartCard: { display: "flex", flexDirection: "column", alignItems: "center" },
  cardTitle: { color: "var(--text-h)", fontSize: "18px", fontWeight: "750", marginBottom: "20px", alignSelf: "flex-start" },
  chartWrapper: { margin: "12px 0 24px 0" },
  chartExplain: { fontSize: "13px", lineHeight: "1.4", color: "var(--text)", textAlign: "center", marginBottom: "24px" },
  statusBox: { display: "flex", alignItems: "center", gap: "10px", borderTop: "1px solid var(--border)", width: "100%", paddingTop: "16px", justifyContent: "center" },
  statusLabelSmall: { fontSize: "13px", fontWeight: "600" },
  recentCard: { display: "flex", flexDirection: "column" },
  emptyText: { color: "var(--text)", fontSize: "14px", textAlign: "center", padding: "40px" },
  msgList: { display: "flex", flexDirection: "column", gap: "14px" },
  msgItem: { borderBottom: "1px solid var(--border)", paddingBottom: "12px" },
  msgItemHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" },
  msgGame: { fontSize: "13px", fontWeight: "600", color: "var(--text-h)" },
  msgBody: { margin: "0 0 6px 0", fontSize: "14px", color: "var(--text-h)", fontStyle: "italic", textAlign: "left" },
  msgDate: { fontSize: "11px", color: "var(--text)", display: "block", textAlign: "left" },
  loading: { display: "flex", justifyContent: "center", alignItems: "center", minHeight: "40vh" },
  error: { backgroundColor: "var(--status-toxic-bg)", color: "var(--status-toxic)", padding: "12px", borderRadius: "8px", textAlign: "center" },
};
