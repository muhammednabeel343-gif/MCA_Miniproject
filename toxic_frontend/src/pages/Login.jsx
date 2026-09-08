import { useState, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { API_BASE_URL } from "../config";
import { setToken, setUser } from "../utils/auth";
import { ShieldMark } from "./Landing";

// Keep authentication logic unchanged, only restyle the page for gaming feel

export default function Login() {
  const [usernameOrEmail, setUsernameOrEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [info, setInfo] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (location.state && location.state.message) {
      setInfo(location.state.message);
    }
  }, [location]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setError(null);
    setInfo(null);

    const cleanInput = usernameOrEmail.trim();

    if (!cleanInput || !password) {
      setError("Please fill in all fields.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username_or_email: cleanInput,
          password: password,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Login failed.");
      }

      // Store Auth data
      setToken(data.token);
      setUser(data.user);

      // Routing distribution based on role
      if (data.user.role === "ADMIN") {
        navigate("/admin?tab=overview");
      } else {
        navigate("/lobby");
      }
      
      // Force page header refresh to render user context
      window.location.reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-layout auth-page" style={styles.outer}>
      <div className="landing-grid" aria-hidden="true" />
      <div className="auth-brand">
        <ShieldMark />
        <span>TOXIC-SHIELD</span>
      </div>

      <div className="card glass auth-card" style={styles.card}>

        <h2 style={styles.title}>Welcome Back</h2>
        <p style={styles.subtitle}>Sign in to enter the arena and keep chats safe.</p>

        {info && <div style={styles.infoBanner}>{info}</div>}
        {error && <div style={styles.errorBanner}>{error}</div>}

        <form onSubmit={handleLogin} style={styles.form}>
          <div style={styles.formGroup}>
            <label style={styles.label}>Username or Email</label>
            <input
              type="text"
              placeholder="Username or email address"
              value={usernameOrEmail}
              onChange={(e) => setUsernameOrEmail(e.target.value)}
              style={styles.input}
              required
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Password</label>
            <input
              type="password"
              placeholder="Enter your password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={styles.input}
              required
            />
          </div>

          <button type="submit" disabled={loading} style={styles.submitBtn}>
            {loading ? "Logging in..." : "Enter Arena"}
          </button>
        </form>

        <p style={styles.footerText}>
          New here? {" "}
          <Link to="/register" style={styles.link}>
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}

const styles = {
  card: {
    width: "100%",
    maxWidth: "400px",
    padding: "36px",
    display: "flex",
    flexDirection: "column",
  },
  outer: {
    padding:'72px 20px 96px'
  },
  title: {
    color: "var(--text-h)",
    fontSize: "24px",
    fontWeight: "700",
    marginBottom: "8px",
    textAlign: "center",
  },
  subtitle: {
    color: "var(--text)",
    fontSize: "14px",
    lineHeight: "1.4",
    marginBottom: "24px",
    textAlign: "center",
  },
  infoBanner: {
    backgroundColor: "var(--status-safe-bg)",
    color: "var(--status-safe)",
    border: "1px solid rgba(16, 185, 129, 0.2)",
    borderRadius: "8px",
    padding: "10px 14px",
    fontSize: "13px",
    marginBottom: "20px",
    textAlign: "center",
    fontWeight: "500",
  },
  errorBanner: {
    backgroundColor: "var(--status-toxic-bg)",
    color: "var(--status-toxic)",
    border: "1px solid rgba(239, 68, 68, 0.2)",
    borderRadius: "8px",
    padding: "10px 14px",
    fontSize: "13px",
    marginBottom: "20px",
    textAlign: "center",
    fontWeight: "500",
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "16px",
  },
  formGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
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
  submitBtn: {
    backgroundColor: "var(--accent)",
    color: "#fff",
    padding: "12px",
    borderRadius: "8px",
    fontWeight: "600",
    fontSize: "15px",
    marginTop: "10px",
    transition: "background-color 0.2s",
    boxShadow: "0 6px 20px rgba(168, 85, 247, 0.25)",
  },
  footerText: {
    marginTop: "24px",
    fontSize: "14px",
    color: "var(--text)",
    textAlign: "center",
  },
  link: {
    fontWeight: "600",
  },
};
