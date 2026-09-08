import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../config";
import { authHeaders } from "../utils/auth";

const statusLabels = {
  WAITING: "OPEN",
  ACTIVE: "FULL",
  FINISHED: "COMPLETED",
};

export default function Rooms() {
  const [rooms, setRooms] = useState([]);
  const [games, setGames] = useState([]);
  const [selectedGame, setSelectedGame] = useState("");
  const [selectedStatus, setSelectedStatus] = useState("");
  const [dateRange, setDateRange] = useState("");
  const [referenceTime] = useState(() => Date.now());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const loadRooms = async () => {
      try {
        const [roomsResponse, gamesResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/rooms`, { headers: authHeaders() }),
          fetch(`${API_BASE_URL}/games`, { headers: authHeaders() }),
        ]);

        if (!roomsResponse.ok) throw new Error("Could not retrieve game rooms.");
        setRooms(await roomsResponse.json());
        if (gamesResponse.ok) setGames(await gamesResponse.json());
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    loadRooms();
  }, []);

  const joinRoom = async (roomId) => {
    setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/rooms/${roomId}/join`, {
        method: "POST",
        headers: authHeaders(),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Could not join game room.");
      navigate(`/rooms/${roomId}`);
    } catch (err) {
      setError(err.message);
    }
  };

  const filteredRooms = rooms.filter((room) => {
    const roomStatus = statusLabels[room.room_status] || room.room_status;
    const matchesGame = !selectedGame || room.game_name === selectedGame;
    const matchesStatus = !selectedStatus || roomStatus === selectedStatus;
    const created = new Date(room.created_at);
    const age = referenceTime - created.getTime();
    const matchesDate = !dateRange ||
      (dateRange === "today" && age < 24 * 60 * 60 * 1000) ||
      (dateRange === "7" && age < 7 * 24 * 60 * 60 * 1000) ||
      (dateRange === "30" && age < 30 * 24 * 60 * 60 * 1000);
    return matchesGame && matchesStatus && matchesDate;
  });

  if (loading) {
    return <div className="page-loading">Loading game rooms...</div>;
  }

  return (
    <div className="app-page rooms-page">
      <div className="page-grid" aria-hidden="true" />
      <div className="page-content">
        <header className="page-header">
          <span className="eyebrow">MULTIPLAYER / ROOM BROWSER</span>
          <h1>Game Rooms</h1>
          <p>Browse, filter, and join available game rooms.</p>
        </header>

        {error && <div className="page-error">{error}</div>}

        <section className="filter-panel">
          <label>Filter by Game<select value={selectedGame} onChange={(event) => setSelectedGame(event.target.value)}><option value="">All Games</option>{games.map((game) => <option key={game.id} value={game.name}>{game.name}</option>)}</select></label>
          <label>Filter by Status<select value={selectedStatus} onChange={(event) => setSelectedStatus(event.target.value)}><option value="">All Rooms</option><option value="OPEN">Open</option><option value="FULL">Full</option><option value="CLOSED">Closed</option><option value="COMPLETED">Completed</option></select></label>
          <label>Filter by Date<select value={dateRange} onChange={(event) => setDateRange(event.target.value)}><option value="">All Dates</option><option value="today">Today</option><option value="7">Last 7 Days</option><option value="30">Last 30 Days</option></select></label>
        </section>

        <section className="rooms-results">
          <div className="section-heading"><h2>Available Rooms</h2><span>{filteredRooms.length} rooms</span></div>
          {filteredRooms.length === 0 ? <div className="empty-panel">No rooms match the selected filters.</div> : (
            <div className="record-scroll room-browser-list">
              {filteredRooms.map((room) => {
                const status = statusLabels[room.room_status] || room.room_status;
                const isJoinable = status === "OPEN" && room.active_players < room.max_players;
                return (
                  <article className="room-browser-item" key={room.id}>
                    <div className="room-browser-main"><h3>{room.room_name}</h3><div className="room-browser-meta"><span className="badge badge-neutral">{room.game_name}</span><span>Created by {room.created_by || "Player"}</span><span>Players: {room.active_players} / {room.max_players}</span><span className={`room-status room-status-${status.toLowerCase()}`}>{status}</span></div><time dateTime={room.created_at}>Created {new Date(room.created_at).toLocaleString()}</time></div>
                    <button className="action-primary room-join-button" disabled={!isJoinable} onClick={() => joinRoom(room.id)}>{isJoinable ? "Join Game" : status === "FULL" ? "Full" : status}</button>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
