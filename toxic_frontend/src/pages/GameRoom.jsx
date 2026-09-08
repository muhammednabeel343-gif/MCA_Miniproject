import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { API_BASE_URL, WS_BASE_URL } from "../config";
import { authHeaders, getToken, getUser } from "../utils/auth";
import { Chess } from "chess.js";

export default function GameRoom() {
  const { roomId } = useParams();
  const navigate = useNavigate();
  const currentUser = getUser();
  const token = getToken();

  const [room, setRoom] = useState(null);
  const [messages, setMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [error, setError] = useState(null);
  const [restriction, setRestriction] = useState(null);
  const [warningMsg, setWarningMsg] = useState(null);
  const [gameState, setGameState] = useState(null);
  const [socketStatus, setSocketStatus] = useState("connecting");
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 1024);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const roomShellRef = useRef(null);

const socketRef = useRef(null);
const messagesAreaRef = useRef(null);
const warningTimerRef = useRef(null);
const restrictionTimerRef = useRef(null);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 1024);
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  useEffect(() => {
    if (!currentUser || !token) {
      navigate("/login");
      return;
    }

    let isActive = true;

    const initializeRoom = async () => {
      await fetchRoomData(isActive);
      if (!isActive) return;
      connectWebSocket(isActive);
    };

    initializeRoom();

    return () => {
      isActive = false;

      if (warningTimerRef.current) {
        clearTimeout(warningTimerRef.current);
        warningTimerRef.current = null;
      }
      if (restrictionTimerRef.current) {
  clearTimeout(restrictionTimerRef.current);
  restrictionTimerRef.current = null;
}
      const ws = socketRef.current;
      if (ws) {
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;

        if (
          ws.readyState === WebSocket.OPEN ||
          ws.readyState === WebSocket.CONNECTING
        ) {
          ws.close();
        }

        if (socketRef.current === ws) {
          socketRef.current = null;
        }
      }
    };
  }, [roomId, token, navigate]);

  useEffect(() => {
    const messagesArea = messagesAreaRef.current;
    if (messagesArea) {
      messagesArea.scrollTo({ top: messagesArea.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  const fetchRoomData = async (isActive = true) => {
    try {
      setError(null);
      const response = await fetch(`${API_BASE_URL}/rooms/${roomId}`, {
        headers: authHeaders(),
      });

      if (!response.ok) throw new Error("Room not found.");

      const data = await response.json();
      if (isActive) setRoom(data);
    } catch (err) {
      console.error("Room loading error:", err);
      if (isActive) setError(err.message || "Could not load game room.");
    }
  };

  const startRestrictionTimer = (message) => {
  setRestriction(message);

  // Remove an old timer if one already exists
  if (restrictionTimerRef.current) {
    clearTimeout(restrictionTimerRef.current);
  }

  // Automatically unlock after 5 minutes
  restrictionTimerRef.current = setTimeout(() => {
    setRestriction(null);

    setWarningMsg(
      "Restriction expired. You can send messages again."
    );

    restrictionTimerRef.current = null;
  }, 5 * 60 * 1000);
};

  const connectWebSocket = (isActive = true) => {
    if (!token) {
      if (isActive) {
        setError("Authentication token is missing.");
        setSocketStatus("disconnected");
      }
      return;
    }


    const previousSocket = socketRef.current;
    if (previousSocket) {
      previousSocket.onopen = null;
      previousSocket.onmessage = null;
      previousSocket.onerror = null;
      previousSocket.onclose = null;

      if (
        previousSocket.readyState === WebSocket.OPEN ||
        previousSocket.readyState === WebSocket.CONNECTING
      ) {
        previousSocket.close();
      }

      if (socketRef.current === previousSocket) {
        socketRef.current = null;
      }
    }

    try {
      if (isActive) setSocketStatus("connecting");

      const wsUrl = `${WS_BASE_URL}/ws/chat/${roomId}?token=${encodeURIComponent(token)}`;
      console.log("Connecting WebSocket:", wsUrl);

      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        if (!isActive || socketRef.current !== ws) return;
        console.log("WebSocket connected successfully.");
        setSocketStatus("connected");
        setWarningMsg(null);
      };

      ws.onmessage = (event) => {
        if (!isActive || socketRef.current !== ws) return;

        try {
          const data = JSON.parse(event.data);

          if (data.type === "chat") {
            setMessages((prev) => [...prev, data]);

            if (data.username === currentUser?.username) {
              if (data.warning_triggered) {
                setWarningMsg(
                  "Automated warning issued: Toxicity detected. Please keep the conversation friendly."
                );

                if (warningTimerRef.current) {
                  clearTimeout(warningTimerRef.current);
                }

                warningTimerRef.current = setTimeout(() => {
                  setWarningMsg(null);
                  warningTimerRef.current = null;
                }, 10000);
              }

              if (data.restriction_triggered) {
  startRestrictionTimer(
    "Chat Restricted: You have been muted for 5 minutes due to repeated toxicity violations."
  );
}
            }
          } else if (data.type === "system") {
            setMessages((prev) => [...prev, data]);

        if (data.status === "Restricted" || data.status === "RESTRICTED") {
  startRestrictionTimer(
    "Chat Restricted: You are currently muted. Game viewing and moves are still allowed."
  );
}
            // If server notified a room status update (start/close), handle it
            if (data.room_status) {
              if (data.room_status === 'FINISHED' || data.room_status === 'CLOSED') {
                setError('This room has been closed by the host.');
                setTimeout(() => navigate('/play-lobby'), 1500);
                return;
              }
              fetchRoomData(isActive);
            }

            if (data.message?.includes("entered the room")) {
              fetchRoomData(isActive);
            }
          } else if (data.type === "game_move") {
            setGameState(data.state);
          }
        } catch (parseError) {
          console.error("WebSocket message parsing error:", parseError);
        }
      };

      ws.onerror = (event) => {
        console.error("WebSocket error:", event);
        if (!isActive || socketRef.current !== ws) return;
        setSocketStatus("error");
      };

      ws.onclose = (event) => {
        console.log("WebSocket closed:", event.code, event.reason);
        if (!isActive || socketRef.current !== ws) return;

        socketRef.current = null;
        setSocketStatus("disconnected");

        if (event.reason === "Invalid token") {
          setError("Your login session has expired. Please log in again.");
          setTimeout(() => navigate("/login"), 2000);
          return;
        }

        if (event.reason === "User not found") {
          setError("Your user account could not be found.");
          return;
        }

        if (event.reason === "Room does not exist") {
          setError("This game room no longer exists.");
          return;
        }

        if (event.code !== 1000 && event.code !== 1001) {
          setWarningMsg(
            "Real-time connection was interrupted. Please refresh the page to reconnect."
          );
        }
      };
    } catch (err) {
      console.error("WebSocket setup error:", err);
      if (isActive) {
        setSocketStatus("error");
        setWarningMsg("Could not start the real-time connection.");
      }
    }
  };

  const handleSendChat = (e) => {
    e.preventDefault();
    const message = chatInput.trim();

    if (!message || restriction) return;

    const ws = socketRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setWarningMsg("Chat connection is not ready. Please wait or refresh.");
      return;
    }

    ws.send(JSON.stringify({ type: "chat", message }));
    setChatInput("");
  };

  const sendGameMove = (updatedState) => {
    setGameState(updatedState);

    const ws = socketRef.current;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "game_move", state: updatedState }));
    }
  };

  const handleLeaveRoom = async () => {
    try {
      await fetch(`${API_BASE_URL}/rooms/${roomId}/leave`, {
        method: "POST",
        headers: authHeaders(),
      });
    } catch (err) {
      console.error("Error leaving room:", err);
    } finally {
      const ws = socketRef.current;
      if (ws) {
        ws.onopen = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.onclose = null;
        if (
          ws.readyState === WebSocket.OPEN ||
          ws.readyState === WebSocket.CONNECTING
        ) {
          ws.close();
        }
        socketRef.current = null;
      }
      navigate("/play-lobby");
    }
  };

  const toggleFullscreen = async () => {
    try {
      if (document.fullscreenElement) {
        await document.exitFullscreen();
      } else {
        await roomShellRef.current?.requestFullscreen();
      }
    } catch (err) {
      console.error("Fullscreen error:", err);
    }
  };

  useEffect(() => {
    const handleFullscreenChange = () => setIsFullscreen(Boolean(document.fullscreenElement));
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  if (error) {
    return (
      <div style={styles.errorContainer}>
        <div style={styles.errorHeader}>{error}</div>
        <button onClick={() => navigate("/play-lobby")} style={styles.lobbyBtn}>
          Back to Lobby
        </button>
      </div>
    );
  }

  if (!room) {
    return (
      <div style={styles.loadingContainer}>
        <div className="counter">Loading game room...</div>
      </div>
    );
  }

  const players = room.players || [];
  const gameName = room.game_name || room.game?.name || "";
  const minimumPlayers = gameName.toLowerCase().includes("snake") && !gameName.toLowerCase().includes("snakes") ? 1 : 2;
  const isHost = room.created_by === currentUser?.username;
  const gameStarted = room.room_status === "ACTIVE";
  const hasEnoughPlayers = players.length >= minimumPlayers;
  const roomStatusLabel = gameStarted ? "GAME IN PROGRESS" : hasEnoughPlayers ? "READY TO START" : "WAITING FOR PLAYERS";
  const currentGridStyle = {
    ...styles.mainGrid,
    gridTemplateColumns: isMobile ? "1fr" : "1.8fr 1.2fr",
    minHeight: isMobile ? "auto" : "min(680px, calc(100vh - 220px))",
    alignItems: isMobile ? "start" : "stretch",
  };

  return (
    <div ref={roomShellRef} className={`room-shell ${isFullscreen ? "room-shell-fullscreen" : ""}`} style={styles.container}>
      <header style={styles.header}>
        <div style={styles.headerTitleArea}>
            {isHost && (
              <div style={{display:'flex',gap:8}}>
                {room.room_status === 'WAITING' && (
                  <button className={hasEnoughPlayers ? "start-ready" : "start-disabled"} disabled={!hasEnoughPlayers} onClick={async ()=>{
                    try{
                      const res = await fetch(`${API_BASE_URL}/rooms/${roomId}/start`,{ method: 'POST', headers: authHeaders() });
                      if(!res.ok) throw new Error(await res.text());
                      // refresh room
                      await fetchRoomData();
                    }catch(err){ alert(err.message || err); }
                  }} style={{...styles.controlBtn, ...(hasEnoughPlayers ? styles.startReadyBtn : styles.startDisabledBtn)}}>Start Game</button>
                )}
                <button onClick={async ()=>{
                  if(!confirm('Close this room for all players?')) return;
                  try{
                    const res = await fetch(`${API_BASE_URL}/rooms/${roomId}/close`,{ method:'POST', headers: authHeaders() });
                    if(!res.ok) throw new Error(await res.text());
                    // after close, navigate back to lobby
                    navigate('/play-lobby');
                  }catch(err){ alert(err.message || err); }
                }} style={{...styles.controlBtn, backgroundColor:'var(--status-toxic-bg)'}}>Close Room</button>
              </div>
            )}
            <button onClick={handleLeaveRoom} style={styles.leaveControlBtn}>
              ← Leave Room
            </button>
            <button onClick={toggleFullscreen} className="fullscreen-control" style={{...styles.leaveControlBtn, marginLeft: 8}}>
              {isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
            </button>
        </div>

        <div style={styles.playersArea}>
          <span style={styles.playersLabel}>Players:</span>
          {players.map((player, index) => (
            <span key={player.id || index} style={styles.playerTag}>
              {player.username}
            </span>
          ))}
        </div>
      </header>

      {warningMsg && <div style={styles.warningBox}>{warningMsg}</div>}
      {restriction && <div style={styles.restrictionBox}>{restriction}</div>}

      <div style={currentGridStyle} className="room-main-grid">
        <div className="card glass game-area" style={styles.gameArea}>
          <div style={styles.gameTitle}>
            {gameName}
          </div>

          {!gameStarted && <div className="game-waiting-overlay"><strong>{hasEnoughPlayers ? "Ready to start" : `Waiting for ${minimumPlayers - players.length} more player${minimumPlayers - players.length === 1 ? "" : "s"}`}</strong><span>{isHost ? "Start the game when everyone is ready." : "Waiting for the host to start the game."}</span></div>}

          <GameManager
            gameName={gameName}
            gameState={gameState}
            sendGameMove={sendGameMove}
            currentUser={currentUser}
            players={players}
            gameStarted={gameStarted}
          />
        </div>

        <div className="game-chat" style={styles.chatArea}>
          <div style={styles.chatHeader}>
            <h3>Game Chat</h3>
            <span
              style={{
                ...styles.socketStatus,
                color:
                  socketStatus === "connected"
                    ? "var(--status-safe)"
                    : "var(--status-toxic)",
              }}
            >
              {socketStatus === "connected"
                ? "● Connected"
                : socketStatus === "connecting"
                ? "● Connecting..."
                : "● Disconnected"}
            </span>
          </div>

          <div ref={messagesAreaRef} style={styles.messagesArea}>
  {messages.length === 0 ? (
    <div style={styles.emptyMessages}>
      No messages yet. Start the conversation.
    </div>
  ) : (
    messages.map((m, index) => {
      const isOwn = m.username === currentUser?.username;
      const isSystem = m.username === "System";
      const isToxic = m.status === "Toxic";

      return (
        <div
          key={`${m.timestamp || index}-${index}`}
          style={{
            ...styles.messageRow,
            justifyContent: isOwn ? "flex-end" : "flex-start",
          }}
        >
          <div
            style={{
              ...styles.messageBubble,
              ...(isOwn ? styles.ownBubble : {}),
              ...(isSystem ? styles.systemBubble : {}),
            }}
          >
            <div style={styles.msgHeader}>
              <span style={styles.msgUser}>{m.username}</span>

              {isToxic && (
                <span
                  className="badge badge-toxic"
                  style={styles.toxicBadge}
                >
                  {m.prediction || "other_cyberbullying"} ({m.confidence}%)
                </span>
              )}
            </div>

            <p style={styles.msgText}>{m.message}</p>
          </div>
        </div>
      );
    })
  )}
</div>

          <form onSubmit={handleSendChat} style={styles.chatForm}>
            <input
              type="text"
              placeholder={
                restriction
                  ? "You are restricted..."
                  : socketStatus === "connected"
                  ? "Type a message..."
                  : "Connecting to chat..."
              }
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              disabled={!!restriction || socketStatus !== "connected"}
              style={styles.chatInput}
            />

            <button
              type="submit"
              disabled={
                !!restriction ||
                socketStatus !== "connected" ||
                !chatInput.trim()
              }
              style={{
                ...styles.sendBtn,
                opacity:
                  restriction ||
                  socketStatus !== "connected" ||
                  !chatInput.trim()
                    ? 0.6
                    : 1,
              }}
            >
              Send
            </button>
          </form>
        </div>
      </div>

    </div>
  );
}

function GameManager({ gameName, gameState, sendGameMove, currentUser, players, gameStarted }) {
  const cleanName = gameName.toLowerCase();

  if (cleanName.includes("tic-tac-toe")) {
    return <TicTacToe state={gameState} sendMove={sendGameMove} currentUser={currentUser} players={players} gameStarted={gameStarted} />;
  }
  if (cleanName.includes("connect four")) {
    return <ConnectFour state={gameState} sendMove={sendGameMove} currentUser={currentUser} players={players} gameStarted={gameStarted} />;
  }
  if (cleanName.includes("snakes and ladders")) {
    return <SnakesAndLadders state={gameState} sendMove={sendGameMove} currentUser={currentUser} players={players} gameStarted={gameStarted} />;
  }
  if (cleanName.includes("chess")) {
    return <ChessGame state={gameState} sendMove={sendGameMove} currentUser={currentUser} players={players} gameStarted={gameStarted} />;
  }
  if (cleanName.includes("ludo")) {
    return <LudoGame state={gameState} sendMove={sendGameMove} currentUser={currentUser} players={players} gameStarted={gameStarted} />;
  }
  if (cleanName.includes("snake")) {
    return <RetroSnakeGame gameStarted={gameStarted} />;
  }
  return <div style={styles.loadingText}>Loading Game Workspace...</div>;
}

function CapturedPieces({ pieces }) {
  const capturedByWhite = pieces.filter((piece) => piece === piece.toLowerCase());
  const capturedByBlack = pieces.filter((piece) => piece === piece.toUpperCase());
  const renderPieces = (captured) => captured.length ? captured.map((piece, index) => <span key={`${piece}-${index}`}>{getChessPieceSymbol(piece)}</span>) : <small>None</small>;
  return <aside className="captured-side-column" aria-label="Captured pieces"><section className="captured-pieces captured-black-side" aria-label="White captured pieces"><strong>White Captured</strong><div>{renderPieces(capturedByBlack)}</div></section><section className="captured-pieces captured-white-side" aria-label="Black captured pieces"><strong>Black Captured</strong><div>{renderPieces(capturedByWhite)}</div></section></aside>;
}

/* const chessInitialBoard = [
  "r", "n", "b", "q", "k", "b", "n", "r", "p", "p", "p", "p", "p", "p", "p", "p",
  null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null,
  null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null,
  "P", "P", "P", "P", "P", "P", "P", "P", "R", "N", "B", "Q", "K", "B", "N", "R"
];

const chessPieceColor = (piece) => piece && (piece === piece.toUpperCase() ? "white" : "black");
const chessCoordinates = (index) => [Math.floor(index / 8), index % 8];
const chessIndex = (row, column) => row >= 0 && row < 8 && column >= 0 && column < 8 ? row * 8 + column : -1;

function getChessMoves(board, origin) {

  const clickSquare = (index) => {
    if (!gameStarted || paused || gameOver || !isMyTurn) return;
    if (selected !== null && possibleMoves.includes(index)) {
      const nextBoard = [...board];
      const captured = nextBoard[index];
      nextBoard[index] = nextBoard[selected];
      nextBoard[selected] = null;
      const capturedKing = captured?.toLowerCase() === "k";
      emitState({ board: nextBoard, isWhiteNext: !isWhiteNext, gameOver: capturedKing, winner: capturedKing ? (isWhiteNext ? white : black) : null });
      resetSelection();
      return;
    }
    const piece = board[index];
    if (piece && chessPieceColor(piece) === myColor) {
      setSelected(index);
      setPossibleMoves(getChessMoves(board, index));
    } else resetSelection();
  };
  const newGame = () => { if (confirm("Start a new chess game?")) { emitState({ board: chessInitialBoard, isWhiteNext: true, gameOver: false, paused: false, winner: null, resignedBy: null }); resetSelection(); } };
  const pauseGame = () => emitState({ ...state, board, paused: true });
  const resumeGame = () => emitState({ ...state, board, paused: false });
  return <div style={gameStyles.wrapper}>
    <div style={gameStyles.turnInfo}><strong>{statusText}</strong> <span>| Your Color: {myColor ? myColor[0].toUpperCase() + myColor.slice(1) : "Spectator"}</span></div>
    {paused && <div className="chess-paused-overlay">Game Paused</div>}
    <div className="chess-controls"><button className="chess-control-new" onClick={newGame}>New Game</button><button className="chess-control-pause" onClick={pauseGame} disabled={paused || gameOver}>Pause</button><button className="chess-control-resume" onClick={resumeGame} disabled={!paused || gameOver}>Resume</button></div>
    <div className="chessBoard" style={gameStyles.chessBoard}>{board.map((piece, index) => { const [row, column] = chessCoordinates(index); const isTarget = possibleMoves.includes(index); const isCapture = isTarget && Boolean(piece); return <button key={index} onClick={() => clickSquare(index)} aria-label={`Chess square ${index + 1}`} style={{ ...gameStyles.chessCell, backgroundColor: (row + column) % 2 === 0 ? "#f0d9b5" : "#b58863", outline: selected === index ? "3px solid #7c3aed" : isCapture ? "3px solid #ef4444" : "none", boxShadow: isTarget && !isCapture ? "inset 0 0 0 10px rgba(124,58,237,.35)" : "none" }}>{piece && getChessPieceSymbol(piece)}{isTarget && !isCapture && <span className="chess-move-dot" />}</button>; })}</div>
      <p style={gameStyles.smallHint}>Select a piece to see legal moves. Check, castling, en passant, and promotion are not implemented.</p>
    </div>;
}

} */

const chessInitialBoard = ["r", "n", "b", "q", "k", "b", "n", "r", "p", "p", "p", "p", "p", "p", "p", "p", ...Array(32).fill(null), "P", "P", "P", "P", "P", "P", "P", "P", "R", "N", "B", "Q", "K", "B", "N", "R"];
const chessPieceColor = (piece) => piece && (piece === piece.toUpperCase() ? "white" : "black");
const chessSquare = (row, column) => row >= 0 && row < 8 && column >= 0 && column < 8 ? row * 8 + column : -1;
function chessMoves(board, origin) {
  const piece = board[origin]; if (!piece) return [];
  const row = Math.floor(origin / 8), column = origin % 8, color = chessPieceColor(piece), moves = [];
  const step = (targetRow, targetColumn) => { const target = chessSquare(targetRow, targetColumn); if (target < 0) return false; if (!board[target] || chessPieceColor(board[target]) !== color) moves.push(target); return !board[target]; };
  const slide = (directions) => directions.forEach(([rowStep, columnStep]) => { let targetRow = row + rowStep, targetColumn = column + columnStep; while (step(targetRow, targetColumn)) { targetRow += rowStep; targetColumn += columnStep; } });
  switch (piece.toLowerCase()) {
    case "p": { const direction = color === "white" ? -1 : 1, forward = chessSquare(row + direction, column); if (forward >= 0 && !board[forward]) { moves.push(forward); const double = chessSquare(row + direction * 2, column); if ((color === "white" ? row === 6 : row === 1) && double >= 0 && !board[double]) moves.push(double); } [-1, 1].forEach((columnStep) => { const target = chessSquare(row + direction, column + columnStep); if (target >= 0 && board[target] && chessPieceColor(board[target]) !== color) moves.push(target); }); break; }
    case "n": [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]].forEach(([rowStep, columnStep]) => step(row + rowStep, column + columnStep)); break;
    case "b": slide([[-1, -1], [-1, 1], [1, -1], [1, 1]]); break;
    case "r": slide([[-1, 0], [1, 0], [0, -1], [0, 1]]); break;
    case "q": slide([[-1, -1], [-1, 1], [1, -1], [1, 1], [-1, 0], [1, 0], [0, -1], [0, 1]]); break;
    case "k": [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]].forEach(([rowStep, columnStep]) => step(row + rowStep, column + columnStep)); break;
    default: break;
  }
  return moves;
}
const CHESS_START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1";
const chessFiles = "abcdefgh";

function chessBoardToFen(board) {
  const rows = [];
  for (let row = 0; row < 8; row += 1) {
    let empty = 0;
    let fenRow = "";
    for (let column = 0; column < 8; column += 1) {
      const piece = board[row * 8 + column];
      if (!piece) empty += 1;
      else { if (empty) fenRow += empty; empty = 0; fenRow += piece; }
    }
    if (empty) fenRow += empty;
    rows.push(fenRow);
  }
  return `${rows.join("/")} w - - 0 1`;
}

function chessEngineBoardToArray(chess) {
  return chess.board().flat().map((piece) => piece ? (piece.color === "w" ? piece.type.toUpperCase() : piece.type) : null);
}

function createChessEngine(state) {
  try {
    if (state?.moveHistory?.length) {
      const chess = new Chess();
      state.moveHistory.forEach((move) => chess.move({ from: move.from, to: move.to, promotion: move.promotion }));
      return chess;
    }
    return new Chess(state?.fen || (state?.board ? chessBoardToFen(state.board) : CHESS_START_FEN));
  } catch {
    return new Chess(state?.fen || CHESS_START_FEN);
  }
}

function ChessGame({ state, sendMove, currentUser, players, gameStarted }) {
  const board = state?.board || chessEngineBoardToArray(new Chess());
  const chess = createChessEngine(state);
  const [selected, setSelected] = useState(null);
  const [promotion, setPromotion] = useState(null);
  const white = players[0]?.username || "White";
  const black = players[1]?.username || "Black";
  const myColor = currentUser?.username === white ? "w" : currentUser?.username === black ? "b" : null;
  const isMyTurn = myColor === chess.turn();
  const legalMoves = selected ? chess.moves({ square: selected, verbose: true }) : [];
  const legalTargets = legalMoves.map((move) => move.to);
  const capturedPieces = state?.capturedPieces || [];

  const clearSelection = () => { setSelected(null); setPromotion(null); };
  const publish = (nextState) => sendMove({ ...nextState, board: chessEngineBoardToArray(createChessEngine(nextState)), paused: Boolean(nextState.paused), gameOver: Boolean(nextState.gameOver) });

  const applyMove = (from, to, promotionPiece) => {
    const nextChess = createChessEngine(state);
    const captured = nextChess.get(to);
    const move = nextChess.move({ from, to, ...(promotionPiece ? { promotion: promotionPiece } : {}) });
    if (!move) return;
    const nextHistory = [...(state?.moveHistory || []), { from, to, promotion: promotionPiece || null, san: move.san }];
    const nextCaptured = captured ? [...capturedPieces, captured.color === "w" ? captured.type.toUpperCase() : captured.type] : capturedPieces;
    const isCheckmate = nextChess.isCheckmate();
    const isStalemate = nextChess.isStalemate();
    const isThreefold = nextChess.isThreefoldRepetition();
    const isFiftyMove = nextChess.isDraw() && nextChess.history().length > 0 && Number(nextChess.fen().split(" ")[4]) >= 100;
    const isInsufficient = nextChess.isInsufficientMaterial();
    const drawReason = isStalemate ? "Draw by Stalemate" : isThreefold ? "Draw by Threefold Repetition" : isFiftyMove ? "Draw by Fifty-Move Rule" : isInsufficient ? "Draw by Insufficient Material" : null;
    const finished = isCheckmate || Boolean(drawReason);
    const mover = move.color === "w" ? white : black;
    publish({
      fen: nextChess.fen(), isWhiteNext: nextChess.turn() === "w", moveHistory: nextHistory,
      capturedPieces: nextCaptured, castlingRights: nextChess.fen().split(" ")[2], enPassantTarget: nextChess.fen().split(" ")[3],
      halfMoveClock: Number(nextChess.fen().split(" ")[4]), positionHistory: [...(state?.positionHistory || []), nextChess.fen()],
      paused: false, gameOver: finished, gameStatus: isCheckmate ? "Checkmate" : drawReason || (nextChess.isCheck() ? "Check" : "In Progress"),
      drawReason, winner: isCheckmate ? mover : null, resignedBy: null, lastMove: move.san,
    });
    clearSelection();
  };

  const selectSquare = (square) => {
    if (!gameStarted || state?.paused || state?.gameOver || !isMyTurn) return;
    if (selected && legalTargets.includes(square)) {
      const selectedMove = legalMoves.find((move) => move.to === square);
      if (selectedMove?.promotion) setPromotion({ from: selected, to: square });
      else applyMove(selected, square);
      return;
    }
    const piece = chess.get(square);
    if (piece?.color === myColor) setSelected(square);
    else clearSelection();
  };

  const resetGame = () => {
    const nextChess = new Chess();
    publish({ fen: nextChess.fen(), isWhiteNext: true, moveHistory: [], capturedPieces: [], castlingRights: "KQkq", enPassantTarget: null, halfMoveClock: 0, positionHistory: [nextChess.fen()], paused: false, gameOver: false, gameStatus: "In Progress", drawReason: null, winner: null, resignedBy: null });
    clearSelection();
  };

  const status = state?.gameStatus === "Checkmate" ? `Checkmate - Winner: ${state.winner}` : state?.drawReason || (state?.paused ? "Game Paused" : `${chess.turn() === "w" ? "White" : "Black"}'s Turn${chess.isCheck() ? " - Check!" : ""}`);
  return <div className="chess-game" style={gameStyles.wrapper}><div style={gameStyles.turnInfo}><strong>{status}</strong><span> | Your Color: {myColor === "w" ? "White" : myColor === "b" ? "Black" : "Spectator"}{isMyTurn && !state?.paused && !state?.gameOver ? " | Your Turn" : ""}</span></div><div className="chess-controls"><button className="chess-control-new" onClick={() => { if (confirm("Start a new chess game?")) resetGame(); }}>New Game</button><button className="chess-control-pause" onClick={() => publish({ ...state, fen: chess.fen(), paused: true })} disabled={state?.paused || state?.gameOver}>Pause</button><button className="chess-control-resume" onClick={() => publish({ ...state, fen: chess.fen(), paused: false })} disabled={!state?.paused || state?.gameOver}>Resume</button></div><div className="chess-board-layout"><div className="chessBoard" style={gameStyles.chessBoard}>{board.map((piece, index) => { const square = `${chessFiles[index % 8]}${8 - Math.floor(index / 8)}`; const isTarget = legalTargets.includes(square); const isCapture = isTarget && Boolean(chess.get(square)); const isCheckedKing = chess.isCheck() && chess.get(square)?.type === "k" && chess.get(square)?.color === chess.turn(); return <button key={square} type="button" onClick={() => selectSquare(square)} style={{ ...gameStyles.chessCell, backgroundColor: (Math.floor(index / 8) + index % 8) % 2 === 0 ? "#f0d9b5" : "#b58863", outline: selected === square ? "3px solid #7c3aed" : isCheckedKing ? "3px solid #ef4444" : isCapture ? "3px solid #ef4444" : "none", boxShadow: isTarget && !isCapture ? "inset 0 0 0 10px rgba(124,58,237,.35)" : "none" }}>{piece && getChessPieceSymbol(piece)}{isTarget && !isCapture && <span className="chess-move-dot" />}</button>; })}</div><CapturedPieces pieces={capturedPieces} /></div>{promotion && <div className="chess-promotion"><strong>Choose promotion</strong>{["q", "r", "b", "n"].map((piece) => <button key={piece} type="button" onClick={() => applyMove(promotion.from, promotion.to, piece)}>{getChessPieceSymbol(myColor === "w" ? piece.toUpperCase() : piece)}</button>)}</div>}{state?.paused && <div className="chess-paused-overlay">Game Paused</div>}<p style={gameStyles.smallHint}>Full legal movement, check, checkmate, castling, en passant, promotion, and draw detection are enabled.</p></div>;
}

function RulesChessGame({ state, sendMove, currentUser, players, gameStarted }) {
  const navigate = useNavigate(), board = state?.board || chessInitialBoard, isWhiteNext = state?.isWhiteNext !== undefined ? state.isWhiteNext : true;
  const white = players[0]?.username || "White", black = players[1]?.username || "Black", myColor = currentUser?.username === white ? "white" : currentUser?.username === black ? "black" : null, isMyTurn = (isWhiteNext && myColor === "white") || (!isWhiteNext && myColor === "black");
  const [selected, setSelected] = useState(null), [moves, setMoves] = useState([]), paused = Boolean(state?.paused), gameOver = Boolean(state?.gameOver);
  const clearSelection = () => { setSelected(null); setMoves([]); };
  const publish = (next) => sendMove({ ...next, paused: Boolean(next.paused), gameOver: Boolean(next.gameOver) });
  const clickSquare = (index) => { if (!gameStarted || paused || gameOver || !isMyTurn) return; if (selected !== null && moves.includes(index)) { const nextBoard = [...board], captured = nextBoard[index]; nextBoard[index] = nextBoard[selected]; nextBoard[selected] = null; const capturedKing = captured?.toLowerCase() === "k"; publish({ board: nextBoard, isWhiteNext: !isWhiteNext, gameOver: capturedKing, winner: capturedKing ? (isWhiteNext ? white : black) : null, capturedPiece: captured || null, capturedBy: captured ? currentUser?.username : null, capturedPieces: captured ? [...(state?.capturedPieces || []), captured] : (state?.capturedPieces || []) }); clearSelection(); return; } const piece = board[index]; if (piece && chessPieceColor(piece) === myColor) { setSelected(index); setMoves(chessMoves(board, index)); } else clearSelection(); };
  const reset = () => { publish({ board: [...chessInitialBoard], isWhiteNext: true, paused: false, gameOver: false, winner: null, resignedBy: null, capturedPieces: [] }); clearSelection(); };
  const status = gameOver ? `Winner: ${state.winner || "unknown"}${state.resignedBy ? ` (${state.resignedBy} resigned)` : ""}` : paused ? "Game Paused" : `${isWhiteNext ? "White" : "Black"}'s Turn`;
  return <div style={gameStyles.wrapper}><div style={gameStyles.turnInfo}><strong>{status}</strong><span> | Your Color: {myColor || "Spectator"}</span></div><div className="chess-controls"><button onClick={() => { if (confirm("Start a new chess game?")) reset(); }}>New Game</button><button onClick={() => publish({ ...state, board, paused: true })} disabled={paused || gameOver}>Pause</button><button onClick={() => publish({ ...state, board, paused: false })} disabled={!paused || gameOver}>Resume</button><button onClick={() => { if (confirm("Restart the current chess game?")) reset(); }}>Restart</button><button onClick={() => { if (confirm("Resign this game?")) publish({ ...state, board, gameOver: true, winner: myColor === "white" ? black : white, resignedBy: currentUser?.username }); }} disabled={gameOver || !myColor}>Resign</button><button onClick={() => navigate("/play-lobby")}>Menu</button></div><div className="chessBoard" style={gameStyles.chessBoard}>{board.map((piece, index) => { const row = Math.floor(index / 8), column = index % 8, target = moves.includes(index), capture = target && Boolean(piece); return <button key={index} onClick={() => clickSquare(index)} style={{ ...gameStyles.chessCell, backgroundColor: (row + column) % 2 === 0 ? "#f0d9b5" : "#b58863", outline: selected === index ? "3px solid #7c3aed" : capture ? "3px solid #ef4444" : "none" }}>{piece && getChessPieceSymbol(piece)}{target && !capture && <span className="chess-move-dot" />}</button>; })}</div><p style={gameStyles.smallHint}>Basic chess movement enabled. Check, castling, en passant, and promotion are not implemented.</p></div>;
}

function SnakesAndLadders({ state, sendMove, currentUser, players, gameStarted }) {
  const p1=players[0]?.username||"Player 1", p2=players[1]?.username||"Player 2";
  const pos1=state?.pos1||1, pos2=state?.pos2||1;
  const isP1Turn=state?.isP1Turn!==undefined?state.isP1Turn:true;
  const diceVal=state?.diceVal||1;
  const myTurn=(currentUser?.username===p1&&isP1Turn)||(currentUser?.username===p2&&!isP1Turn);
  const jumps={3:38,9:31,21:42,28:84,51:67,72:91,80:99,17:7,54:34,62:19,64:60,87:36,93:73,95:75,98:79};

  const rollDice=()=>{
    if(!gameStarted||!myTurn||pos1>=100||pos2>=100)return;
    const roll=Math.floor(Math.random()*6)+1;
    let next=(isP1Turn?pos1:pos2)+roll;
    if(next>100)next=isP1Turn?pos1:pos2;
    if(jumps[next])next=jumps[next];
    sendMove({pos1:isP1Turn?next:pos1,pos2:isP1Turn?pos2:next,isP1Turn:!isP1Turn,diceVal:roll});
  };

  return (
    <div style={gameStyles.wrapper}>
      <div style={gameStyles.turnInfo}>{pos1>=100||pos2>=100?<span style={gameStyles.winnerText}>Winner: {pos1>=100?p1:p2}!</span>:<span>Dice: <strong>{diceVal}</strong> | Turn: <strong>{isP1Turn?p1:p2}</strong> {myTurn?"(You)":""}</span>}</div>
      <div style={gameStyles.salBoardFlex}>
        <div style={gameStyles.salGrid}>
          {Array.from({length:100}).map((_,i)=>{
            const cell=100-i, p1Here=pos1===cell, p2Here=pos2===cell;
            const bg=jumps[cell]?(jumps[cell]>cell?"#dcfce7":"#fee2e2"):"var(--bg-input)";
            return <div key={cell} style={{...gameStyles.salCell,backgroundColor:bg}}>
              <span style={gameStyles.salCellNum}>{cell}</span>
              <div style={gameStyles.salTokens}>{p1Here&&<span style={gameStyles.salToken}>P1</span>}{p2Here&&<span style={{...gameStyles.salToken,backgroundColor:"#22c55e"}}>P2</span>}</div>
            </div>;
          })}
        </div>
        <div style={gameStyles.controlsSide}>
          <button onClick={rollDice} disabled={!myTurn} style={gameStyles.rollBtn}>Roll Dice</button>
          {(pos1>=100||pos2>=100)&&<button onClick={()=>sendMove({pos1:1,pos2:1,isP1Turn:true,diceVal:1})} style={gameStyles.resetBtn}>Restart</button>}
        </div>
      </div>
    </div>
  );
}

/* function ChessGame({ state, sendMove, currentUser, players, gameStarted }) {
  const navigate = useNavigate();
  const board = state?.board || chessInitialBoard;
  const isWhiteNext = state?.isWhiteNext !== undefined ? state.isWhiteNext : true;
  const white = players[0]?.username || "White";
  const black = players[1]?.username || "Black";
  const myColor = currentUser?.username === white ? "white" : currentUser?.username === black ? "black" : null;
  const isMyTurn = (isWhiteNext && myColor === "white") || (!isWhiteNext && myColor === "black");
  const paused = Boolean(state?.paused);
  const gameOver = Boolean(state?.gameOver);
  const [selected, setSelected] = useState(null);
  const [moves, setMoves] = useState([]);

  const clearSelection = () => {
    setSelected(null);
    setMoves([]);
  };

  const paused = Boolean(state?.paused) || false;
  const gameOver = Boolean(state?.gameOver) || false;
    paused: Boolean(nextState.paused),
    gameOver: Boolean(nextState.gameOver),
  });

  const resetGame = () => {
    publish({ board: [...chessInitialBoard], isWhiteNext: true, paused: false, gameOver: false, winner: null, resignedBy: null, result: null });
    clearSelection();
  };

  const selectSquare = (index) => {
    if (!gameStarted || paused || gameOver || !isMyTurn) return;

    if (selected !== null && moves.includes(index)) {
      const nextBoard = [...board];
      const captured = nextBoard[index];
      nextBoard[index] = nextBoard[selected];
      nextBoard[selected] = null;
      const capturedKing = captured?.toLowerCase() === "k";
      publish({ board: nextBoard, isWhiteNext: !isWhiteNext, paused: false, gameOver: capturedKing, winner: capturedKing ? (isWhiteNext ? white : black) : null, resignedBy: null, result: capturedKing ? "king-captured" : null });
      clearSelection();
      return;
    }

    const piece = board[index];
    if (piece && chessPieceColor(piece) === myColor) {
      setSelected(index);
      setMoves(chessMoves(board, index));
    } else {
      clearSelection();
    }
  };

  const status = gameOver
    ? `Game Over: ${state.winner ? `Winner: ${state.winner}` : "Draw"}${state.resignedBy ? ` (${state.resignedBy} resigned)` : ""}`
    : paused ? "Game Paused" : `${isWhiteNext ? "White" : "Black"}'s Turn`;

  return (
    <div style={gameStyles.wrapper}>
      <div style={gameStyles.turnInfo}>
        <strong>{status}</strong>
        <span> | Your Color: {myColor ? myColor[0].toUpperCase() + myColor.slice(1) : "Spectator"}</span>
      </div>
      <div className="chess-controls">
        <button onClick={() => { if (confirm("Start a new chess game?")) resetGame(); }}>New Game</button>
        <button onClick={() => publish({ ...state, board, paused: true })} disabled={paused || gameOver}>Pause</button>
        <button onClick={() => publish({ ...state, board, paused: false })} disabled={!paused || gameOver}>Resume</button>
        <button onClick={() => { if (confirm("Restart the current game?")) resetGame(); }}>Restart</button>
        <button onClick={() => { if (confirm("Resign this game?")) { publish({ ...state, board, paused: false, gameOver: true, winner: myColor === "white" ? black : white, resignedBy: currentUser?.username, result: "resigned" }); clearSelection(); } }} disabled={gameOver || !myColor}>Resign</button>
        <button onClick={() => navigate("/play-lobby")}>Menu / Exit Game</button>
      </div>
      <div className="chessBoard" style={gameStyles.chessBoard}>
        {board.map((piece, index) => {
          const row = Math.floor(index / 8);
          const column = index % 8;
          const isTarget = moves.includes(index);
          const isCapture = isTarget && Boolean(piece);
          return <button key={index} type="button" onClick={() => selectSquare(index)} aria-label={`Chess square ${index + 1}`} style={{ ...gameStyles.chessCell, backgroundColor: (row + column) % 2 === 0 ? "#f0d9b5" : "#b58863", outline: selected === index ? "3px solid #7c3aed" : isCapture ? "3px solid #ef4444" : "none", boxShadow: isTarget && !isCapture ? "inset 0 0 0 10px rgba(124,58,237,.35)" : "none" }}>{piece && getChessPieceSymbol(piece)}{isTarget && !isCapture && <span className="chess-move-dot" />}</button>;
        })}
      </div>
      {paused && <div className="chess-paused-overlay">Game Paused</div>}
      <p style={gameStyles.smallHint}>Basic movement is enabled. Check, checkmate, castling, en passant, and promotion are not implemented.</p>
    </div>
  );
  const myColor=currentUser?.username===white?"white":currentUser?.username===black?"black":null;
  const isMyTurn=(isWhiteNext&&myColor==="white")||(!isWhiteNext&&myColor==="black");
  const [selected,setSelected]=useState(null);

  const clickSquare=(index)=>{
    if(!gameStarted || !isMyTurn)return;
    const piece=board[index];
    const own=piece&&((piece===piece.toUpperCase())===isWhiteNext);
    if(selected===null){
      if(own)setSelected(index);
    const chessInitialBoard = [
      "r", "n", "b", "q", "k", "b", "n", "r", "p", "p", "p", "p", "p", "p", "p", "p",
      null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null,
      null, null, null, null, null, null, null, null, null, null, null, null, null, null, null, null,
      "P", "P", "P", "P", "P", "P", "P", "P", "R", "N", "B", "Q", "K", "B", "N", "R"
    ];
    const chessPieceColor = (piece) => piece && (piece === piece.toUpperCase() ? "white" : "black");
    const chessCoordinates = (index) => [Math.floor(index / 8), index % 8];
    const chessIndex = (row, column) => row >= 0 && row < 8 && column >= 0 && column < 8 ? row * 8 + column : -1;

    function getChessMoves(board, origin) {
      const piece = board[origin];
      if (!piece) return [];
      const [row, column] = chessCoordinates(origin);
      const color = chessPieceColor(piece);
      const moves = [];
      const addStep = (targetRow, targetColumn) => {
        const target = chessIndex(targetRow, targetColumn);
        if (target < 0) return false;
        if (!board[target] || chessPieceColor(board[target]) !== color) moves.push(target);
        return !board[target];
      };
      const addSlides = (directions) => directions.forEach(([rowStep, columnStep]) => {
        let targetRow = row + rowStep;
        let targetColumn = column + columnStep;
        while (addStep(targetRow, targetColumn)) { targetRow += rowStep; targetColumn += columnStep; }
      });

      switch (piece.toLowerCase()) {
        case "p": {
          const direction = color === "white" ? -1 : 1;
          const oneForward = chessIndex(row + direction, column);
          if (oneForward >= 0 && !board[oneForward]) {
            moves.push(oneForward);
            const startRow = color === "white" ? 6 : 1;
            const twoForward = chessIndex(row + direction * 2, column);
            if (row === startRow && twoForward >= 0 && !board[twoForward]) moves.push(twoForward);
          }
          [-1, 1].forEach((columnStep) => {
            const target = chessIndex(row + direction, column + columnStep);
            if (target >= 0 && board[target] && chessPieceColor(board[target]) !== color) moves.push(target);
          });
          break;
        }
        case "n": [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]].forEach(([rowStep, columnStep]) => addStep(row + rowStep, column + columnStep)); break;
        case "b": addSlides([[-1, -1], [-1, 1], [1, -1], [1, 1]]); break;
        case "r": addSlides([[-1, 0], [1, 0], [0, -1], [0, 1]]); break;
        case "q": addSlides([[-1, -1], [-1, 1], [1, -1], [1, 1], [-1, 0], [1, 0], [0, -1], [0, 1]]); break;
        case "k": [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]].forEach(([rowStep, columnStep]) => addStep(row + rowStep, column + columnStep)); break;
        default: break;
      }
      return moves;
    }

  };

  return (
    <div style={gameStyles.wrapper}>
      <div style={gameStyles.turnInfo}>Turn: <strong>{isWhiteNext?white:black}</strong> {isMyTurn?"(You)":""}</div>
      <div className="chessBoard" style={gameStyles.chessBoard}>
        {board.map((piece,index)=>{
          const row=Math.floor(index/8),col=index%8;
          return <button key={index} onClick={()=>clickSquare(index)} style={{...gameStyles.chessCell,backgroundColor:(row+col)%2===0?"#f0d9b5":"#b58863",outline:selected===index?"3px solid #7c3aed":"none"}}>{piece&&getChessPieceSymbol(piece)}</button>;
        })}
      </div>
      <p style={gameStyles.smallHint}>Simplified project chess: select your piece, then select the destination.</p>
    </div>
  );
}

} */

/* const chessInitialBoard = ["r", "n", "b", "q", "k", "b", "n", "r", "p", "p", "p", "p", "p", "p", "p", "p", ...Array(32).fill(null), "P", "P", "P", "P", "P", "P", "P", "P", "R", "N", "B", "Q", "K", "B", "N", "R"];
const chessPieceColor = (piece) => piece && (piece === piece.toUpperCase() ? "white" : "black");
const chessSquare = (row, column) => row >= 0 && row < 8 && column >= 0 && column < 8 ? row * 8 + column : -1;

function chessMoves(board, origin) {
  const piece = board[origin];
  if (!piece) return [];

  const row = Math.floor(origin / 8);
  const column = origin % 8;
  const color = chessPieceColor(piece);
  const moves = [];

  const addStep = (targetRow, targetColumn) => {
    const target = chessSquare(targetRow, targetColumn);
    if (target < 0) return false;
    if (!board[target]) {
      moves.push(target);
      return true;
    }
    if (chessPieceColor(board[target]) !== color) moves.push(target);
    return false;
  };

  const addSlides = (directions) => directions.forEach(([rowStep, columnStep]) => {
    let targetRow = row + rowStep;
    let targetColumn = column + columnStep;
    while (addStep(targetRow, targetColumn)) {
      targetRow += rowStep;
      targetColumn += columnStep;
    }
  });

  switch (piece.toLowerCase()) {
    case "p": {
      const direction = color === "white" ? -1 : 1;
      const startRow = color === "white" ? 6 : 1;
      const forward = chessSquare(row + direction, column);
      if (forward >= 0 && !board[forward]) {
        moves.push(forward);
        const double = chessSquare(row + direction * 2, column);
        if (row === startRow && double >= 0 && !board[double]) moves.push(double);
      }
      [-1, 1].forEach((columnStep) => {
        const target = chessSquare(row + direction, column + columnStep);
        if (target >= 0 && board[target] && chessPieceColor(board[target]) !== color) moves.push(target);
      });
      break;
    }
    case "n":
      [[-2, -1], [-2, 1], [-1, -2], [-1, 2], [1, -2], [1, 2], [2, -1], [2, 1]]
        .forEach(([rowStep, columnStep]) => addStep(row + rowStep, column + columnStep));
      break;
    case "b": addSlides([[-1, -1], [-1, 1], [1, -1], [1, 1]]); break;
    case "r": addSlides([[-1, 0], [1, 0], [0, -1], [0, 1]]); break;
    case "q": addSlides([[-1, -1], [-1, 1], [1, -1], [1, 1], [-1, 0], [1, 0], [0, -1], [0, 1]]); break;
    case "k":
      [[-1, -1], [-1, 0], [-1, 1], [0, -1], [0, 1], [1, -1], [1, 0], [1, 1]]
        .forEach(([rowStep, columnStep]) => addStep(row + rowStep, column + columnStep));
      break;
    default: break;
  }
  return moves;
}

function ChessGame({ state, sendMove, currentUser, players, gameStarted }) {
  const navigate = useNavigate(), board = state?.board || chessInitialBoard, isWhiteNext = state?.isWhiteNext !== undefined ? state.isWhiteNext : true;
  const white = players[0]?.username || "White", black = players[1]?.username || "Black", myColor = currentUser?.username === white ? "white" : currentUser?.username === black ? "black" : null, isMyTurn = (isWhiteNext && myColor === "white") || (!isWhiteNext && myColor === "black");
  const [selected, setSelected] = useState(null), [moves, setMoves] = useState([]), paused = Boolean(state?.paused), gameOver = Boolean(state?.gameOver);
  const publish = (next) => sendMove({ ...next, paused: Boolean(next.paused), gameOver: Boolean(next.gameOver) });
  const clearSelection = () => { setSelected(null); setMoves([]); };
  const selectSquare = (index) => { if (!gameStarted || paused || gameOver || !isMyTurn) return; if (selected !== null && moves.includes(index)) { const nextBoard = [...board]; const captured = nextBoard[index]; nextBoard[index] = nextBoard[selected]; nextBoard[selected] = null; publish({ board: nextBoard, isWhiteNext: !isWhiteNext, gameOver: captured?.toLowerCase() === "k", winner: captured?.toLowerCase() === "k" ? (isWhiteNext ? white : black) : null }); clearSelection(); return; } const piece = board[index]; if (piece && chessPieceColor(piece) === myColor) { setSelected(index); setMoves(chessMoves(board, index)); } else clearSelection(); };
  const reset = () => publish({ board: chessInitialBoard, isWhiteNext: true, paused: false, gameOver: false, winner: null, resignedBy: null });
  const status = gameOver ? `Winner: ${state.winner || "unknown"}${state.resignedBy ? ` (${state.resignedBy} resigned)` : ""}` : paused ? "Game Paused" : `${isWhiteNext ? "White" : "Black"}'s Turn`;
  return <div style={gameStyles.wrapper}><div style={gameStyles.turnInfo}><strong>{status}</strong><span> | Your Color: {myColor || "Spectator"}</span></div><div className="chess-controls"><button onClick={() => { if (confirm("Start a new chess game?")) { reset(); clearSelection(); } }}>New Game</button><button onClick={() => publish({ ...state, board, paused: true })} disabled={paused || gameOver}>Pause</button><button onClick={() => publish({ ...state, board, paused: false })} disabled={!paused || gameOver}>Resume</button><button onClick={() => { if (confirm("Restart the current chess game?")) { reset(); clearSelection(); } }}>Restart</button><button onClick={() => { if (confirm("Resign this game?")) publish({ ...state, board, gameOver: true, winner: myColor === "white" ? black : white, resignedBy: currentUser?.username }); }} disabled={gameOver || !myColor}>Resign</button><button onClick={() => navigate("/play-lobby")}>Menu</button></div><div className="chessBoard" style={gameStyles.chessBoard}>{board.map((piece, index) => { const row = Math.floor(index / 8), column = index % 8, target = moves.includes(index), capture = target && Boolean(piece); return <button key={index} onClick={() => selectSquare(index)} style={{ ...gameStyles.chessCell, backgroundColor: (row + column) % 2 === 0 ? "#f0d9b5" : "#b58863", outline: selected === index ? "3px solid #7c3aed" : capture ? "3px solid #ef4444" : "none" }}>{piece && getChessPieceSymbol(piece)}{target && !capture && <span className="chess-move-dot" />}</button>; })}</div><p style={gameStyles.smallHint}>Basic chess movement enabled. Check, castling, en passant, and promotion are not implemented.</p></div>;
}

} */

function getChessPieceSymbol(char) {
  return ({R:"♖",N:"♘",B:"♗",Q:"♕",K:"♔",P:"♙",r:"♜",n:"♞",b:"♝",q:"♛",k:"♚",p:"♟"})[char]||"";
}

function LudoGame({ state, sendMove, currentUser, players, gameStarted }) {
  const p1=players[0]?.username||"Gamer 1", p2=players[1]?.username||"Gamer 2";
  const pos1=state?.pos1||0,pos2=state?.pos2||0;
  const isP1Next=state?.isP1Next!==undefined?state.isP1Next:true;
  const rolled=state?.rolled||null;
  const isMyTurn=(currentUser?.username===p1&&isP1Next)||(currentUser?.username===p2&&!isP1Next);

  const roll=()=>{
    if(!gameStarted||!isMyTurn||pos1>=30||pos2>=30)return;
    const value=Math.floor(Math.random()*6)+1;
    let target=(isP1Next?pos1:pos2)+value;
    if(target>30)target=isP1Next?pos1:pos2;
    sendMove({pos1:isP1Next?target:pos1,pos2:isP1Next?pos2:target,isP1Next:!isP1Next,rolled:value});
  };

  return (
    <div style={gameStyles.wrapper}>
      <div style={gameStyles.turnInfo}>{pos1>=30||pos2>=30?<span style={gameStyles.winnerText}>Winner: {pos1>=30?p1:p2}!</span>:<span>Dice: <strong>{rolled||"?"}</strong> | Turn: <strong>{isP1Next?p1:p2}</strong> {isMyTurn?"(You)":""}</span>}</div>
      <div style={gameStyles.ludoBoard}>
        <div style={gameStyles.ludoTracks}>
          {Array.from({length:31}).map((_,step)=><div key={step} style={{...gameStyles.ludoTrackCell,backgroundColor:step===30?"#dcfce7":"var(--bg-input)"}}>{step===30?"🏆":step}{pos1===step&&<span style={gameStyles.ludoP1}>●</span>}{pos2===step&&<span style={gameStyles.ludoP2}>●</span>}</div>)}
        </div>
        <button onClick={roll} disabled={!isMyTurn} style={gameStyles.rollBtn}>Roll Dice</button>
      </div>
    </div>
  );
}

function RetroSnakeGame({ gameStarted }) {
  const canvasRef=useRef(null);
  const [score,setScore]=useState(0);
  const [isPlaying,setIsPlaying]=useState(false);
  const [gameState,setGameState]=useState("START");

  useEffect(()=>{
    if(!isPlaying)return;
    const canvas=canvasRef.current;if(!canvas)return;
    const ctx=canvas.getContext("2d");
    const size=20, grid=20;
    let snake=[{x:10,y:10}],dir={x:0,y:-1},food={x:5,y:5},currentScore=0;
    const key=(e)=>{
      if(e.key==="ArrowUp"&&dir.y!==1)dir={x:0,y:-1};
      if(e.key==="ArrowDown"&&dir.y!==-1)dir={x:0,y:1};
      if(e.key==="ArrowLeft"&&dir.x!==1)dir={x:-1,y:0};
      if(e.key==="ArrowRight"&&dir.x!==-1)dir={x:1,y:0};
    };
    window.addEventListener("keydown",key);
    const interval=setInterval(()=>{
      const head={x:snake[0].x+dir.x,y:snake[0].y+dir.y};
      if(head.x<0||head.x>=grid||head.y<0||head.y>=grid||snake.some(s=>s.x===head.x&&s.y===head.y)){
        setIsPlaying(false);setGameState("GAME_OVER");clearInterval(interval);return;
      }
      snake.unshift(head);
      if(head.x===food.x&&head.y===food.y){currentScore+=10;setScore(currentScore);food={x:Math.floor(Math.random()*grid),y:Math.floor(Math.random()*grid)};}
      else snake.pop();
      ctx.fillStyle="#0c0d14";ctx.fillRect(0,0,canvas.width,canvas.height);
      ctx.fillStyle="#ef4444";ctx.fillRect(food.x*size,food.y*size,size-2,size-2);
      ctx.fillStyle="#8b5cf6";snake.forEach(p=>ctx.fillRect(p.x*size,p.y*size,size-2,size-2));
    },150);
    return()=>{window.removeEventListener("keydown",key);clearInterval(interval);};
  },[isPlaying]);

  const start=()=>{if (!gameStarted) return; setScore(0);setGameState("PLAY");setIsPlaying(true);};

  return <div style={gameStyles.wrapper}>
    <div style={gameStyles.turnInfo}>Arcade Score: <strong>{score}</strong></div>
    <div className="snakeCanvasWrapper" style={gameStyles.snakeCanvasWrapper}>
      {gameState!=="PLAY"&&<div style={gameStyles.canvasOverlay}><h3>{gameState==="START"?"SNAKE RETRO MODE":"GAME OVER"}</h3><button onClick={start} style={gameStyles.rollBtn}>{gameState==="START"?"Start Game":"Play Again"}</button></div>}
      <canvas ref={canvasRef} width="400" height="400" style={gameStyles.canvas}/>
    </div>
  </div>;
}

const styles = {
  container:{padding:"20px 0",display:"flex",flexDirection:"column",gap:"20px"},
  loadingContainer:{minHeight:"60vh",display:"flex",alignItems:"center",justifyContent:"center"},
  errorContainer:{padding:"40px",textAlign:"center"},
  errorHeader:{color:"var(--status-toxic)",marginBottom:"20px"},
  lobbyBtn:{padding:"10px 18px"},
  header:{display:"flex",justifyContent:"space-between",alignItems:"center",gap:"16px",flexWrap:"wrap",borderBottom:"1px solid var(--border)",paddingBottom:"12px"},
  headerTitleArea:{display:"flex",alignItems:"center",gap:"16px"},
  backBtn:{backgroundColor:"transparent",color:"var(--text)",fontSize:"14px",fontWeight:"600"},
  leaveControlBtn:{backgroundColor:"var(--bg-input)",color:"var(--text-h)",border:"1px solid var(--border)",padding:"8px 12px",borderRadius:8,fontSize:"13px",fontWeight:700,cursor:"pointer"},
  roomName:{color:"var(--text-h)",fontSize:"20px",margin:0},
  controlBtn:{padding:'8px 12px',borderRadius:8,color:'var(--text)',border:'none',cursor:'pointer',fontWeight:700},
  playersArea:{display:"flex",alignItems:"center",gap:"8px",flexWrap:"wrap"},
  playersLabel:{fontSize:"13px",fontWeight:"600",color:"var(--text)"},
  playerTag:{backgroundColor:"var(--border)",color:"var(--text-h)",padding:"4px 10px",borderRadius:"10px",fontSize:"12px",fontWeight:"600"},
  warningBox:{padding:"12px",borderRadius:"8px",background:"#fef3c7",color:"#92400e"},
  restrictionBox:{padding:"12px",borderRadius:"8px",background:"#fee2e2",color:"#991b1b"},
  waitingBox:{marginBottom:"16px",padding:"10px 14px",borderRadius:"8px",background:"var(--bg-input)",fontSize:"13px"},
  mainGrid:{display:"grid",gap:"12px"},
  gameArea:{padding:"24px",display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"flex-start",minWidth:0,overflow:"auto",height:"100%"},
  gameTitle:{color:"var(--text-h)",fontSize:"20px",fontWeight:"700",marginBottom:"16px"},
  chatArea:{display:"flex",flexDirection:"column",padding:0,backgroundColor:"var(--bg-panel)",border:"1px solid var(--border)",borderRadius:"12px",overflow:"hidden",height:"100%",minHeight:0},
  chatHeader:{padding:"16px",borderBottom:"1px solid var(--border)",display:"flex",justifyContent:"space-between",alignItems:"center"},
  socketStatus:{fontSize:"12px",fontWeight:"600"},
  messagesArea:{flex:"1 1 0",minHeight:0,overflowY:"auto",padding:"16px",display:"flex",flexDirection:"column",gap:"10px"},
  emptyMessages:{textAlign:"center",color:"var(--text)",marginTop:"30px"},
  messageRow:{display:"flex"},
  messageBubble:{maxWidth:"85%",padding:"10px 12px",borderRadius:"10px",background:"var(--bg-input)"},
  ownBubble:{background:"rgba(124,58,237,0.16)"},
  systemBubble:{background:"rgba(34,197,94,0.12)"},
  msgHeader:{display:"flex",gap:"8px",alignItems:"center",marginBottom:"4px"},
  msgUser:{fontSize:"12px",fontWeight:"700",color:"var(--text-h)"},
  toxicBadge:{fontSize:"10px"},
  msgText:{margin:0,fontSize:"14px",wordBreak:"break-word"},
  chatForm:{display:"flex",gap:"10px",padding:"14px",borderTop:"1px solid var(--border)"},
  chatInput:{flex:1,minWidth:0},
  sendBtn:{padding:"10px 16px"},
  loadingText:{padding:"30px",color:"var(--text)"}
};

const gameStyles = {
  wrapper:{width:"100%",display:"flex",flexDirection:"column",alignItems:"center",gap:"16px"},
  turnInfo:{padding:"10px 14px",background:"var(--bg-input)",borderRadius:"8px",color:"var(--text-h)",textAlign:"center"},
  winnerText:{fontWeight:"800",color:"var(--status-safe)"},
  resetBtn:{padding:"10px 18px"},
  rollBtn:{padding:"10px 18px"},
  tttBoard:{display:"grid",gridTemplateColumns:"repeat(3,90px)",gap:"6px"},
  tttCell:{width:"90px",height:"90px",fontSize:"36px",fontWeight:"800"},
  c4Board:{display:"flex",gap:"6px",padding:"10px",background:"#2563eb",borderRadius:"12px"},
  c4Column:{display:"flex",flexDirection:"column",gap:"6px",cursor:"pointer"},
  c4Cell:{width:"48px",height:"48px",borderRadius:"50%"},
  salBoardFlex:{display:"flex",gap:"20px",alignItems:"flex-start",flexWrap:"wrap",justifyContent:"center"},
  salGrid:{display:"grid",gridTemplateColumns:"repeat(10,minmax(34px,1fr))",width:"min(560px,90vw)",border:"1px solid var(--border)"},
  salCell:{minHeight:"42px",border:"1px solid var(--border)",padding:"3px",position:"relative"},
  salCellNum:{fontSize:"9px"},
  salTokens:{display:"flex",gap:"2px",justifyContent:"center"},
  salToken:{fontSize:"9px",padding:"2px 4px",borderRadius:"5px",background:"#7c3aed",color:"#fff"},
  controlsSide:{display:"flex",flexDirection:"column",gap:"10px"},
  chessBoard:{display:"grid",gridTemplateColumns:"repeat(8,minmax(38px,60px))",width:"min(480px,90vw)",aspectRatio:"1"},
  chessCell:{aspectRatio:"1",border:"none",fontSize:"clamp(24px,5vw,42px)",padding:0,cursor:"pointer"},
  smallHint:{fontSize:"12px",color:"var(--text)",textAlign:"center"},
  ludoBoard:{display:"flex",flexDirection:"column",alignItems:"center",gap:"16px",width:"100%"},
  ludoTracks:{display:"grid",gridTemplateColumns:"repeat(8,1fr)",gap:"5px",width:"min(600px,90vw)"},
  ludoTrackCell:{minHeight:"48px",border:"1px solid var(--border)",borderRadius:"8px",padding:"6px",position:"relative",fontSize:"12px"},
  ludoP1:{color:"#7c3aed",marginLeft:"4px"},
  ludoP2:{color:"#22c55e",marginLeft:"4px"},
  snakeCanvasWrapper:{position:"relative",width:"min(400px,90vw)",aspectRatio:"1"},
  canvas:{width:"100%",height:"100%",border:"2px solid var(--border)",background:"#0c0d14"},
  canvasOverlay:{position:"absolute",inset:0,display:"flex",flexDirection:"column",alignItems:"center",justifyContent:"center",gap:"12px",background:"rgba(0,0,0,0.65)",color:"#fff"}
};