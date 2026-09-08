import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../config";
import { ShieldMark } from "./Landing";

export default function Register() {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleRegister = async (e) => {
    e.preventDefault();
    setError(null);

    const cleanUsername = username.trim();
    const cleanEmail = email.trim();

    if (!cleanUsername || !cleanEmail || !password || !confirmPassword) {
      setError("All fields are required.");
      return;
    }

    if (password.length < 4) {
      setError("Password must be at least 4 characters long.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: cleanUsername,
          email: cleanEmail,
          password: password,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "Registration failed.");
      }

      // Successful registration: Redirect client to Login
      navigate("/login", { state: { message: "Account created successfully! Please log in." } });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-layout auth-page register-page" style={styles.outer}>
      <div className="landing-grid" aria-hidden="true" />
      <div className="auth-brand">
        <ShieldMark />
        <span>TOXIC-SHIELD</span>
      </div>

      <div className="card glass auth-card" style={styles.card}>

        <h2 style={styles.title}>Create Account</h2>
        <p style={styles.subtitle}>Sign up to start playing and stay protected with in-chat safety.</p>

        {error && <div style={styles.errorBanner}>{error}</div>}

        <form onSubmit={handleRegister} style={styles.form}>
          <div style={styles.formGroup}>
            <label style={styles.label}>Username</label>
            <input
              type="text"
              placeholder="Enter username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              style={styles.input}
              required
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Email Address</label>
            <input
              type="email"
              placeholder="Enter email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={styles.input}
              required
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Password</label>
            <input
              type="password"
              placeholder="Min 4 characters"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={styles.input}
              required
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>Confirm Password</label>
            <input
              type="password"
              placeholder="Repeat password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              style={styles.input}
              required
            />
          </div>

          <button type="submit" disabled={loading} style={styles.submitBtn}>
            {loading ? "Creating account..." : "Create Account"}
          </button>
        </form>

        <p style={styles.footerText}>
          Already have an account?{" "}
          <Link to="/login" style={styles.link}>
            Login here
          </Link>
        </p>
      </div>
    </div>
  );
}

const styles = {
  card: {
    width: "100%",
    maxWidth: "420px",
    padding: "28px",
    display: "flex",
    flexDirection: "column",
  },
  outer: {
    padding:'40px 20px 96px'
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
    marginBottom: "18px",
    textAlign: "center",
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
    gap: "12px",
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
    marginTop: "6px",
    transition: "background-color 0.2s",
    boxShadow: "0 6px 20px rgba(168, 85, 247, 0.25)",
    ":disabled": {
      opacity: 0.5,
      cursor: "not-allowed",
    },
  },
  footerText: {
    marginTop: "16px",
    fontSize: "14px",
    color: "var(--text)",
    textAlign: "center",
  },
  link: {
    fontWeight: "600",
  },
};
