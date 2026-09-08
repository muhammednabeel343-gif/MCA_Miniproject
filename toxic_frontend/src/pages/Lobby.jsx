import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../config";
import { authHeaders, getUser } from "../utils/auth";

export default function Lobby() {
  const [games, setGames] = useState([]);
  const [selectedGame, setSelectedGame] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  const [roomName, setRoomName] = useState("");
  const [maxPlayers, setMaxPlayers] = useState(2);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const navigate = useNavigate();
  const currentUser = getUser();

  useEffect(() => {
    const user = getUser();

    if (!user) {
      navigate("/login");
      return;
    }

    const controller = new AbortController();

    const fetchLobbyData = async () => {
      setLoading(true);
      setError(null);

      try {
        const gamesRes = await fetch(`${API_BASE_URL}/games`, {
          headers: authHeaders(),
          signal: controller.signal,
        });

        if (!gamesRes.ok) {
          throw new Error("Could not retrieve games.");
        }

        const gamesData = await gamesRes.json();

        if (!controller.signal.aborted) {
          setGames(gamesData);
        }

      } catch (err) {
        if (err.name !== "AbortError" && !controller.signal.aborted) {
          setError(err.message);
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    };

    fetchLobbyData();

    return () => {
      controller.abort();
    };
  }, [navigate]);

  const handleOpenCreateModal = (game) => {
    setSelectedGame(game);
    setRoomName(`${currentUser.username}'s ${game.name} Room`);
    setMaxPlayers(game.max_players);
    setShowCreateModal(true);
  };

  const handleCreateRoom = async (e) => {
    e.preventDefault();
    setError(null);

    if (!roomName.trim()) {
      setError("Room name cannot be empty");
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/rooms`, {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
          game_id: selectedGame.id,
          room_name: roomName.trim(),
          max_players: parseInt(maxPlayers),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not create game room.");
      }

      navigate(`/rooms/${data.id}`);
    } catch (err) {
      setError(err.message);
    }
  };

  if (loading) {
    return (
      <div style={styles.loadingContainer}>
        <div className="counter">Loading lobby data...</div>
      </div>
    );
  }

  return (
    <div className="app-page games-page" style={styles.container}>
      <div className="page-grid" aria-hidden="true" />
      <header style={styles.header}>
        <div>
          <h1 style={styles.title}>Choose Your Game</h1>
          <p style={styles.subtitle}>
              Select a game to create a room and start playing with others.
          </p>
        </div>
      </header>

      {error && <div style={styles.error}>{error}</div>}

      <div className="gridContainer games-only-grid" style={styles.gridContainer}>
        <section style={styles.gamesSection}>
          <h2 style={styles.sectionTitle}>Available Games</h2>

          <div className="gamesGrid" style={styles.gamesGrid}>
            {games.map((game) => (
              <div key={game.id} className="card" style={styles.gameCard}>
                <div style={styles.gameBadge}>{game.game_type}</div>

                <div style={styles.gameIcon}>{getGameIcon(game.name)}</div>

                <h3 style={styles.gameName}>{game.name}</h3>

                <p style={styles.gameDesc}>{game.description}</p>

                <div style={styles.gameFooter}>
                  <span style={styles.playerCount}>
                    {game.min_players === game.max_players
                      ? `${game.min_players} Players`
                      : `${game.min_players}-${game.max_players} Players`}
                  </span>

                  <button
                    onClick={() => handleOpenCreateModal(game)}
                    style={styles.playBtn}
                  >
                    Create Room
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {showCreateModal && (
        <div style={styles.modalOverlay}>
          <div className="card" style={styles.modal}>
            <h2 style={styles.modalTitle}>
              Create {selectedGame?.name} Room
            </h2>

            <form onSubmit={handleCreateRoom} style={styles.modalForm}>
              <div style={styles.formGroup}>
                <label style={styles.label}>Room Name</label>

                <input
                  type="text"
                  value={roomName}
                  onChange={(e) => setRoomName(e.target.value)}
                  style={styles.input}
                  required
                />
              </div>

              <div style={styles.formGroup}>
                <label style={styles.label}>Max Players</label>

                <select
                  value={maxPlayers}
                  onChange={(e) => setMaxPlayers(e.target.value)}
                  style={styles.input}
                >
                  {selectedGame &&
                    Array.from(
                      {
                        length:
                          selectedGame.max_players -
                          selectedGame.min_players +
                          1,
                      },
                      (_, i) => selectedGame.min_players + i
                    ).map((num) => (
                      <option key={num} value={num}>
                        {num} Players
                      </option>
                    ))}
                </select>
              </div>

              <div style={styles.modalButtons}>
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  style={styles.cancelBtn}
                >
                  Cancel
                </button>

                <button type="submit" style={styles.createBtn}>
                  Launch Room
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

function getGameIcon(name) {
  const clean = name.toLowerCase();

  if (clean.includes("tic")) {
    return (
      <svg
        className="svg-icon"
        viewBox="0 0 24 24"
        style={{ width: "32px", height: "32px" }}
      >
        <path
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          d="M1 8h22M1 16h22M8 1v22M16 1v22"
        />
      </svg>
    );
  }

  if (clean.includes("connect")) {
    return (
      <svg
        className="svg-icon"
        viewBox="0 0 24 24"
        style={{ width: "32px", height: "32px" }}
      >
        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-12 4c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 6c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 6c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm5-12c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 6c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 6c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm5-12c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 6c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 6c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2z" />
      </svg>
    );
  }

  if (clean.includes("snakes")) {
    return (
      <svg
        className="svg-icon"
        viewBox="0 0 24 24"
        style={{ width: "32px", height: "32px" }}
      >
        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-2 10H7v-2h10v2zm0-4H7V7h10v2zm0 8H7v-2h10v2z" />
      </svg>
    );
  }

  if (clean.includes("chess")) {
    return (
      <svg
        className="svg-icon"
        viewBox="0 0 24 24"
        style={{ width: "32px", height: "32px" }}
      >
        <path d="M19 3H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-4 12V9c0-1.66-1.34-3-3-3s-3 1.34-3 3v6c0 1.66 1.34 3 3 3s3-1.34 3-3z" />
      </svg>
    );
  }

  if (clean.includes("ludo")) {
    return (
      <svg
        className="svg-icon"
        viewBox="0 0 24 24"
        style={{ width: "32px", height: "32px" }}
      >
        <path d="M19 3H5c-1.11 0-2 .9-2 2v14c0 1.1.89 2 2 2h14c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm-1 11H12v6H6v-6h6V8H6V3h6v5h6v6z" />
      </svg>
    );
  }

  return (
    <svg
      className="svg-icon"
      viewBox="0 0 24 24"
      style={{ width: "32px", height: "32px" }}
    >
      <path d="M7 18c-1.1 0-1.99.9-1.99 2S5.9 22 7 22s2-.9 2-2-.9-2-2-2zM1 2v2h2l3.6 7.59-1.35 2.45c-.16.28-.25.61-.25.96 0 1.1.9 2 2 2h12v-2H7.42c-.14 0-.25-.11-.25-.25l.03-.12.9-1.63h7.45c.75 0 1.41-.41 1.75-1.03l3.58-6.49c.08-.14.12-.31.12-.48 0-.55-.45-1-1-1H5.21l-.94-2H1zm16 16c-1.1 0-1.99.9-1.99 2s.89 2 1.99 2 2-.9 2-2-.9-2-2-2z" />
    </svg>
  );
}

const styles = {
  container: {
    padding: "20px 0",
  },
  header: {
    marginBottom: "36px",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
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
  gridContainer: {
    display: "flex",
    flexDirection: "column",
    gap: "42px",
  },
  gamesSection: {
    display: "flex",
    flexDirection: "column",
  },
  sectionTitle: {
    color: "var(--text-h)",
    fontSize: "20px",
    fontWeight: "600",
    marginBottom: "20px",
    borderBottom: "1px solid var(--border)",
    paddingBottom: "10px",
  },
  gamesGrid: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))",
    gap: "20px",
  },
  gameCard: {
    display: "flex",
    flexDirection: "column",
    position: "relative",
    overflow: "hidden",
    alignItems: "flex-start",
    textAlign: "left",
  },
  gameBadge: {
    position: "absolute",
    top: "14px",
    right: "14px",
    backgroundColor: "var(--border)",
    color: "var(--text)",
    padding: "3px 8px",
    borderRadius: "4px",
    fontSize: "10px",
    fontWeight: "600",
    textTransform: "uppercase",
  },
  gameIcon: {
    color: "var(--accent)",
    marginBottom: "16px",
  },
  gameName: {
    fontSize: "18px",
    fontWeight: "700",
    color: "var(--text-h)",
    margin: "0 0 8px 0",
  },
  gameDesc: {
    fontSize: "13px",
    color: "var(--text)",
    lineHeight: "1.4",
    flex: 1,
    marginBottom: "20px",
  },
  gameFooter: {
    width: "100%",
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
    gap: "14px",
    marginTop: "auto",
  },
  playerCount: {
    fontSize: "13px",
    color: "var(--text-h)",
    fontWeight: "600",
  },
  playBtn: {
    backgroundColor: "var(--accent)",
    color: "#fff",
    padding: "8px 14px",
    borderRadius: "6px",
    fontSize: "13px",
    fontWeight: "600",
    boxShadow: "0 2px 6px rgba(168, 85, 247, 0.2)",
  },
  roomsSection: {
    display: "flex",
    flexDirection: "column",
  },
  emptyRooms: {
    padding: "36px",
    textAlign: "center",
    color: "var(--text)",
    fontSize: "14px",
  },
  roomsList: {
    display: "flex",
    flexDirection: "column",
    gap: "14px",
  },
  roomItem: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "16px 20px",
  },
  roomNameTitle: {
    fontSize: "15px",
    fontWeight: "600",
    color: "var(--text-h)",
    margin: "0 0 4px 0",
  },
  roomMeta: {
    fontSize: "12px",
    color: "var(--text)",
    display: "flex",
    alignItems: "center",
  },
  joinBtn: {
    backgroundColor: "var(--bg-input)",
    color: "var(--text-h)",
    border: "1px solid var(--border)",
    padding: "8px 14px",
    borderRadius: "6px",
    fontSize: "13px",
    fontWeight: "600",
  },
  loadingContainer: {
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
    minHeight: "40vh",
  },
  error: {
    backgroundColor: "var(--status-toxic-bg)",
    color: "var(--status-toxic)",
    padding: "12px",
    borderRadius: "8px",
    marginBottom: "24px",
    textAlign: "center",
    fontWeight: "500",
  },
  modalOverlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.8)",
    zIndex: 999,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  modal: {
    width: "100%",
    maxWidth: "400px",
    padding: "30px",
  },
  modalTitle: {
    color: "var(--text-h)",
    fontSize: "20px",
    fontWeight: "600",
    margin: "0 0 20px 0",
  },
  modalForm: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
  },
  formGroup: {
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
  modalButtons: {
    display: "flex",
    justifyContent: "flex-end",
    gap: "12px",
    marginTop: "10px",
  },
  cancelBtn: {
    backgroundColor: "transparent",
    color: "var(--text)",
    border: "1px solid var(--border)",
    padding: "8px 16px",
    borderRadius: "6px",
    fontSize: "14px",
  },
  createBtn: {
    backgroundColor: "var(--accent)",
    color: "#fff",
    padding: "8px 16px",
    borderRadius: "6px",
    fontSize: "14px",
    fontWeight: "600",
  },
};