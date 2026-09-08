import { useState, useEffect } from "react";
import { API_BASE_URL } from "../config";
import { authHeaders } from "../utils/auth";

export default function History() {
  const [history, setHistory] = useState([]);
  const [games, setGames] = useState([]);

  const [search, setSearch] = useState("");
  const [selectedGame, setSelectedGame] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchHistoryData();
  }, []);

  const fetchHistoryData = async () => {
    setLoading(true);
    setError(null);

    try {
      const historyRes = await fetch(`${API_BASE_URL}/history/me`, {
        headers: authHeaders(),
      });

      if (!historyRes.ok) {
        throw new Error("Could not retrieve history logs.");
      }

      const historyData = await historyRes.json();
      setHistory(historyData);

      const gamesRes = await fetch(`${API_BASE_URL}/games`, {
        headers: authHeaders(),
      });

      if (gamesRes.ok) {
        const gamesData = await gamesRes.json();
        setGames(gamesData);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const filteredHistory = history.filter((item) => {
    const matchesSearch = item.message
      .toLowerCase()
      .includes(search.toLowerCase());

    const matchesGame =
      selectedGame === "" ||
      (item.game_name && item.game_name === selectedGame);

    const matchesStatus =
      selectedStatus === "" ||
      item.status === selectedStatus;

    return matchesSearch && matchesGame && matchesStatus;
  });

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={styles.title}>Chat Audit</h1>

        <p style={styles.subtitle}>
          Review your past messages, classifications, confidence levels, and safety status.
        </p>
      </header>

      {error && <div style={styles.error}>{error}</div>}

      <div className="card glass filterCard" style={styles.filterCard}>
        <div className="filterGrid" style={styles.filterGrid}>
          <div style={styles.filterGroup}>
            <label style={styles.label}>Search Messages</label>

            <input
              type="text"
              placeholder="Type keyword..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={styles.input}
            />
          </div>

          <div style={styles.filterGroup}>
            <label style={styles.label}>Filter by Game</label>

            <select
              value={selectedGame}
              onChange={(e) => setSelectedGame(e.target.value)}
              style={styles.input}
            >
              <option value="">All Games</option>

              {games.map((g) => (
                <option key={g.id} value={g.name}>
                  {g.name}
                </option>
              ))}
            </select>
          </div>

          <div style={styles.filterGroup}>
            <label style={styles.label}>Filter by Status</label>

            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              style={styles.input}
            >
              <option value="">All States</option>
              <option value="Safe">Safe</option>
              <option value="Toxic">Toxic</option>
            </select>
          </div>
        </div>
      </div>

      {loading ? (
        <div style={styles.loading}>
          <span className="counter">Retrieving chat records...</span>
        </div>
      ) : filteredHistory.length === 0 ? (
        <div className="card glass" style={styles.empty}>
          <p>No chat messages match your search filter criteria.</p>
        </div>
      ) : (
        <div className="card record-scroll history-table" style={styles.tableCard}>
          <table className="admin-table">
            <thead>
              <tr>
                <th>Game / Room</th>
                <th>Message Content</th>
                <th>Classification</th>
                <th>Status</th>
                <th>Confidence</th>
                <th>Sent At</th>
              </tr>
            </thead>

            <tbody>
              {filteredHistory.map((item) => (
                <tr key={item.id}>
                  <td>
                    <div style={styles.gameRoomFlex}>
                      <span style={styles.gameText}>
                        {item.game_name || "Lobby"}
                      </span>

                      <span style={styles.roomText}>
                        {item.room_name || "General"}
                      </span>
                    </div>
                  </td>

                  <td style={styles.messageVal}>
                    "{item.message}"
                  </td>

                  <td>{item.prediction}</td>

                  <td>
                    <span
                      className={`badge ${
                        item.status === "Safe"
                          ? "badge-safe"
                          : "badge-toxic"
                      }`}
                    >
                      {item.status}
                    </span>
                  </td>

                  <td>
                    <span style={styles.modelSpan}>
                      {item.confidence}%
                    </span>

                    <span style={styles.modelSub}>
                      {item.selected_model}
                    </span>
                  </td>

                  <td style={styles.dateCell}>
                    {new Date(item.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

const styles = {
  container: {
    padding: "20px 0",
  },

  header: {
    marginBottom: "30px",
  },

  title: {
    fontSize: "28px",
    fontWeight: "700",
    color: "var(--text-h)",
    margin: "0 0 6px 0",
  },

  subtitle: {
    color: "var(--text)",
    fontSize: "14px",
    margin: 0,
  },

  filterCard: {
    padding: "20px 24px",
    marginBottom: "24px",
  },

  filterGrid: {
    display: "grid",
    gridTemplateColumns: "2fr 1fr 1fr",
    gap: "20px",
  },

  filterGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    textAlign: "left",
  },

  label: {
    fontSize: "13px",
    fontWeight: "600",
    color: "var(--text-h)",
  },

  input: {
    width: "100%",
    boxSizing: "border-box",
  },

  loading: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: "30px",
    padding: "40px",
  },

  empty: {
    padding: "48px",
    textAlign: "center",
    color: "var(--text)",
  },

  tableCard: {
    padding: 0,
    backgroundColor: "var(--bg-panel)",
    border: "1px solid var(--border)",
    overflowX: "auto",
  },

  gameRoomFlex: {
    display: "flex",
    flexDirection: "column",
  },

  gameText: {
    color: "var(--text-h)",
    fontWeight: "600",
    fontSize: "14px",
  },

  roomText: {
    fontSize: "12px",
    color: "var(--text)",
  },

  messageVal: {
    fontStyle: "italic",
    maxWidth: "300px",
    wordBreak: "break-word",
  },

  modelSpan: {
    fontWeight: "600",
    color: "var(--text-h)",
  },

  modelSub: {
    fontSize: "10px",
    color: "var(--text)",
    display: "block",
  },

  dateCell: {
    fontSize: "13px",
  },

  error: {
    backgroundColor: "var(--status-toxic-bg)",
    color: "var(--status-toxic)",
    padding: "12px",
    borderRadius: "8px",
    marginBottom: "20px",
    textAlign: "center",
  },
};