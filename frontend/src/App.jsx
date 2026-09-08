import { BrowserRouter as Router, Routes, Route, Link, Navigate, useLocation } from "react-router-dom";
import { getUser, getToken, logout } from "./utils/auth";

// Import Pages
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Lobby from "./pages/Lobby";
import LobbyHome from "./pages/LobbyHome";
import Rooms from "./pages/Rooms";
import GameRoom from "./pages/GameRoom";
import Profile from "./pages/Profile";
import AdminDashboard from "./pages/AdminDashboardRedesigned";
import { ShieldMark } from "./pages/Landing";

// Protected Route Wrapper (Standard Users)
function ProtectedRoute({ children }) {
  const token = getToken();
  if (!token) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

// Admin Route Wrapper (Administrators)
function AdminRoute({ children }) {
  const token = getToken();
  const user = getUser();
  if (!token || !user || user.role !== "ADMIN") {
    return <Navigate to="/lobby" replace />;
  }
  return children;
}

function LandingAwareNavigation({ children }) {
  const location = useLocation();
  const isPublicEntry = ["/", "/login", "/register"].includes(location.pathname);
  return isPublicEntry ? null : children;
}

function AuthNavLink({ to, children }) {
  const location = useLocation();
  const active = location.pathname === to || location.pathname.startsWith(`${to}/`) || (to === "/home" && location.pathname === "/lobby") || (to === "/play-lobby" && location.pathname === "/games");

  return (
    <Link to={to} style={{ ...styles.navLink, ...(active ? styles.activeNavLink : {}) }}>
      {children}
    </Link>
  );
}

const adminTabs = [
  ["overview", "Overview"],
  ["users", "Users"],
  ["flags", "Flagged Messages"],
  ["moderation", "Moderation History"],
];

function AdminNavLink({ tab, children }) {
  const location = useLocation();
  const selectedTab = new URLSearchParams(location.search).get("tab") || "overview";
  const active = location.pathname === "/admin" && selectedTab === tab;

  return (
    <Link
      to={`/admin?tab=${tab}`}
      className={`admin-global-tab${active ? " active" : ""}`}
    >
      {children}
    </Link>
  );
}

function App() {
  const currentUser = getUser();
  const token = getToken();
  const isLoggedIn = !!token && !!currentUser;

  return (
    <Router>
      <div className="app-container">
        <LandingAwareNavigation>
          {/* Global Navigation Header */}
          <nav className="navBar" style={styles.navBar}>
          <div className="navLogo" style={styles.navLogo}>
            <Link to={isLoggedIn && currentUser.role === "ADMIN" ? "/admin?tab=overview" : isLoggedIn ? "/home" : "/"} style={styles.logoLink}>
              <ShieldMark />
              <span>TOXIC-SHIELD</span>
            </Link>
          </div>

          <div className="navLinks" style={styles.navLinks}>
            {isLoggedIn ? (
              <>
                {currentUser.role === "ADMIN" ? (
                  adminTabs.map(([tab, label]) => (
                    <AdminNavLink key={tab} tab={tab}>{label}</AdminNavLink>
                  ))
                ) : (
                  <>
                    <AuthNavLink to="/home">
                      Home
                    </AuthNavLink>
                    <AuthNavLink to="/play-lobby">
                      Play Lobby
                    </AuthNavLink>
                    <AuthNavLink to="/rooms">
                      Rooms
                    </AuthNavLink>
                    <AuthNavLink to="/profile">
                      Profile
                    </AuthNavLink>
                  </>
                )}

                <div className="userInfoArea" style={styles.userInfoArea}>
                  <span style={styles.userBadge}>
                    {currentUser.username} ({currentUser.role})
                  </span>
                  <button onClick={logout} style={styles.logoutBtn}>
                    Logout
                  </button>
                </div>
              </>
            ) : (
              <>
                <Link to="/" style={styles.navLink}>
                  Home
                </Link>
                <Link to="/login" style={styles.navLink}>
                  Login
                </Link>
                <Link to="/register" style={styles.navLink}>
                  Sign Up
                </Link>
              </>
            )}
          </div>
          </nav>
        </LandingAwareNavigation>

        {/* Routers Page Content Panel */}
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route
              path="/home"
              element={
                <ProtectedRoute>
                  <LobbyHome />
                </ProtectedRoute>
              }
            />
            
            {/* Protected Routes */}
            <Route
              path="/play-lobby"
              element={
                <ProtectedRoute>
                  <Lobby />
                </ProtectedRoute>
              }
            />
            <Route path="/lobby" element={<Navigate to="/home" replace />} />
            <Route path="/games" element={<Navigate to="/play-lobby" replace />} />
            <Route path="/history" element={<Navigate to="/chat-audit" replace />} />
            <Route
              path="/rooms"
              element={
                <ProtectedRoute>
                  <Rooms />
                </ProtectedRoute>
              }
            />
            <Route
              path="/rooms/:roomId"
              element={
                <ProtectedRoute>
                  <GameRoom />
                </ProtectedRoute>
              }
            />
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <Profile />
                </ProtectedRoute>
              }
            />
            <Route path="/chat-audit" element={<Navigate to="/admin" replace />} />
            <Route
              path="/admin"
              element={
                <AdminRoute>
                  <AdminDashboard />
                </AdminRoute>
              }
            />

            {/* Default Catch-all */}
            <Route path="*" element={<Navigate to={isLoggedIn ? "/lobby" : "/"} replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

const styles = {
  navBar: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "16px 30px",
    backgroundColor: "var(--bg-panel)",
    borderBottom: "1px solid var(--border)",
  },
  navLogo: {
    fontSize: "18px",
    fontWeight: "800",
    letterSpacing: "0.05em",
  },
  logoLink: {
    color: "var(--text-h)",
    display: "flex",
    alignItems: "center",
    gap: "6px",
  },
  navLinks: {
    display: "flex",
    alignItems: "center",
    gap: "24px",
  },
  navLink: {
    fontSize: "14px",
    fontWeight: "600",
    color: "var(--text)",
    padding: "8px 12px",
    borderRadius: "8px",
    transition: "color 0.2s",
  },
  activeNavLink: {
    color: "var(--text-h)",
    backgroundColor: "var(--accent)",
    boxShadow: "0 5px 16px rgba(168, 85, 247, 0.24)",
  },
  navAdminLink: {
    fontSize: "14px",
    fontWeight: "600",
    color: "var(--status-warn)",
  },
  userInfoArea: {
    display: "flex",
    alignItems: "center",
    gap: "14px",
    borderLeft: "1px solid var(--border)",
    paddingLeft: "24px",
  },
  userBadge: {
    fontSize: "12px",
    fontWeight: "750",
    color: "var(--text-h)",
    backgroundColor: "var(--bg-input)",
    padding: "6px 12px",
    borderRadius: "6px",
    border: "1px solid var(--border)",
  },
  logoutBtn: {
    backgroundColor: "transparent",
    color: "var(--status-toxic)",
    fontSize: "13px",
    fontWeight: "600",
    padding: "6px 12px",
    borderRadius: "6px",
    border: "1px solid rgba(239, 68, 68, 0.2)",
    ":hover": {
      backgroundColor: "var(--status-toxic-bg)",
    },
  },
};

export default App;