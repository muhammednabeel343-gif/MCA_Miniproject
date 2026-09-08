import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API_BASE_URL } from "../config";
import { authHeaders, getUser } from "../utils/auth";

const AdminDashboard = () => {
  const navigate = useNavigate();
  const currentUser = getUser();
  // Admin section sub-menus / sidebar
  const [activeTab, setActiveTab] = useState("overview"); // overview, users, flags, moderation, analytics

  // Data arrays
  const [users, setUsers] = useState([]);
  const [flags, setFlags] = useState([]);
  const [flagsSearch, setFlagsSearch] = useState("");
  const [flagsFilterPrediction, setFlagsFilterPrediction] = useState("");
  const [flagsStartDate, setFlagsStartDate] = useState("");
  const [flagsEndDate, setFlagsEndDate] = useState("");
  const [analytics, setAnalytics] = useState(null);
  const [usersSearch, setUsersSearch] = useState("");
  const [usersFilterStatus, setUsersFilterStatus] = useState("");
  const [usersFilterRole, setUsersFilterRole] = useState("");
  const [selectedUserDetails, setSelectedUserDetails] = useState(null);
  const [moderationActions, setModerationActions] = useState([]);
  const [moderationFilterUser, setModerationFilterUser] = useState("");
  const [moderationLimit, setModerationLimit] = useState(50);
  const [refreshing, setRefreshing] = useState(false);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!currentUser || currentUser.role !== "ADMIN") {
      navigate("/lobby");
      return;
    }
    fetchAdminData();
  }, [navigate]);

  // fetch moderation actions on demand or when moderation tab is active
  const fetchModeration = async (params = {}) => {
    setRefreshing(true);
    try {
      const qs = new URLSearchParams();
      if (params.user_id) qs.set('user_id', params.user_id);
      qs.set('limit', params.limit || moderationLimit);
      const res = await fetch(`${API_BASE_URL}/admin/moderation?${qs.toString()}`, { headers: authHeaders() });
      if (!res.ok) throw new Error('Failed to load moderation actions');
      const data = await res.json();
      setModerationActions(data);
    } catch (err) {
      console.error(err);
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(()=>{
    if(activeTab === 'moderation') fetchModeration();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  const fetchAdminData = async () => {
    setLoading(true);
    setError(null);
    try {
      // 1. Fetch Users
      const usersRes = await fetch(`${API_BASE_URL}/admin/users`, {
        headers: authHeaders(),
      });
      if (!usersRes.ok) throw new Error("Could not retrieve users list.");
      const usersData = await usersRes.json();
      setUsers(usersData);

      // 2. Fetch Flagged toxic chats (default)
      await fetchFlags();

      // 3. Fetch analytics/dashboard metrics
      const analyticsRes = await fetch(`${API_BASE_URL}/admin/dashboard`, {
        headers: authHeaders(),
      });
      if (analyticsRes.ok) {
        const ad = await analyticsRes.json();
        // normalize backend shape to what frontend expects
        setAnalytics({
          total_messages: ad.stats?.total_messages || 0,
          toxic_messages: ad.stats?.toxic_messages || 0,
          safe_messages: ad.stats?.safe_messages || 0,
          total_users: ad.stats?.total_users || 0,
          active_restrictions: ad.stats?.restricted_users || 0,
          toxicity_by_class: ad.charts?.categories || {},
          top_toxic_users: ad.charts?.top_toxic_users || [],
          timeline: ad.charts?.timeline || [],
        });
      }
      // 4. Fetch recent moderation actions
      const modRes = await fetch(`${API_BASE_URL}/admin/moderation?limit=20`, {
        headers: authHeaders(),
      });
      if (modRes.ok) {
        setModerationActions(await modRes.json());
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchFlags = async (params = {}) => {
    const qs = new URLSearchParams();
    if (params.user_id) qs.set('user_id', params.user_id);
    if (params.game_id) qs.set('game_id', params.game_id);
    if (flagsFilterPrediction) qs.set('prediction', flagsFilterPrediction);
    if (flagsStartDate) qs.set('start_date', flagsStartDate);
    if (flagsEndDate) qs.set('end_date', flagsEndDate);
    const url = `${API_BASE_URL}/admin/flagged-messages?${qs.toString()}`;
    try {
      const res = await fetch(url, { headers: authHeaders() });
      if (!res.ok) return;
      const data = await res.json();
      // apply simple client-side search filter on message or username if provided
      const q = flagsSearch.trim().toLowerCase();
      const filtered = q ? data.filter(d => (d.message||'').toLowerCase().includes(q) || (d.username||'').toLowerCase().includes(q)) : data;
      setFlags(filtered);
    } catch (err) {
      console.error('Error fetching flags', err);
    }
  };

  // refetch flags when filters change and flags tab is active
  useEffect(()=>{
    if(activeTab === 'flags') fetchFlags();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, flagsFilterPrediction, flagsStartDate, flagsEndDate]);

  // User moderation actions triggers
  const handleRestrict = async (userId) => {
    const mins = prompt("Enter restrict period in minutes:", "60");
    if (!mins) return;
    const reason = prompt("Reason for restriction:", "Violation of chat rules");
    if (!reason) return;
    try {
      const res = await fetch(`${API_BASE_URL}/admin/users/${userId}/restrict`, {
        method: "PATCH",
        headers: {
          ...authHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ duration_minutes: parseInt(mins, 10), reason }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Failed to restrict user.");
      }
      alert("User restricted successfully.");
      fetchAdminData();
      if (selectedUserDetails && selectedUserDetails.user && selectedUserDetails.user.id === userId) {
        handleViewDetails(userId);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  const handleBlock = async (userId) => {
    if (!confirm("Are you sure you want to BLOCK this user? Access will be revoked.")) return;
    const reason = prompt("Reason for blocking:", "Severe violations");
    if (!reason) return;
    try {
      const res = await fetch(`${API_BASE_URL}/admin/users/${userId}/block`, {
        method: "PATCH",
        headers: {
          ...authHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reason }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Failed to block user.");
      }
      alert("User blocked successfully.");
      fetchAdminData();
      if (selectedUserDetails && selectedUserDetails.user && selectedUserDetails.user.id === userId) {
        handleViewDetails(userId);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  const handleUnblock = async (userId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/admin/users/${userId}/unblock`, {
        method: "PATCH",
        headers: authHeaders(),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Failed to unblock user.");
      }
      alert("User status restored to ACTIVE.");
      fetchAdminData();
      if (selectedUserDetails && selectedUserDetails.user && selectedUserDetails.user.id === userId) {
        handleViewDetails(userId);
      }
    } catch (err) {
      alert(err.message);
    }
  };

  const handleUnrestrict = async (userId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/admin/users/${userId}/unrestrict`, {
        method: "POST",
        headers: {
          ...authHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ reason: "Manual restriction lift by admin" }),
      });
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Failed to remove restriction.");
      }
      alert("User restriction removed successfully.");
      fetchAdminData();
      if (selectedUserDetails?.user?.id === userId) handleViewDetails(userId);
    } catch (err) {
      alert(err.message);
    }
  };

  const handleViewDetails = async (userId) => {
    try {
      const res = await fetch(`${API_BASE_URL}/admin/users/${userId}`, { headers: authHeaders() });
      if (!res.ok) throw new Error('Could not load user details');
      const data = await res.json();
      setSelectedUserDetails(data);
    } catch (err) {
      alert(err.message);
    }
  };

  if (loading) {
    return (
      <div style={styles.loading}>
        <span className="counter">Configuring admin command center...</span>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", gap: "24px" }}>
      {/* Sidebar Navigation */}
      <aside style={styles.sidebar}>
        <div style={styles.sideBrand}>
          <div style={{ fontSize: 20, fontWeight: 800 }}>🛡️ TOXIC-SHIELD</div>
          <div style={{ fontSize: 12, color: "var(--text)", marginTop: 6 }}>Admin Control Center</div>
        </div>

        <nav style={styles.sideNav}>
          <button onClick={() => setActiveTab("overview")} className={`side-btn ${activeTab === "overview" ? "active" : ""}`} style={styles.sideBtn}>
            Overview
          </button>
          <button onClick={() => setActiveTab("users")} className={`side-btn ${activeTab === "users" ? "active" : ""}`} style={styles.sideBtn}>
            Users ({users.length})
          </button>
          <button onClick={() => setActiveTab("flags")} className={`side-btn ${activeTab === "flags" ? "active" : ""}`} style={styles.sideBtn}>
            Flagged Messages ({flags.length})
          </button>
          <button onClick={() => setActiveTab("chatAudit")} className={`side-btn ${activeTab === "chatAudit" ? "active" : ""}`} style={styles.sideBtn}>
            Chat Audit
          </button>
          <button onClick={() => setActiveTab("moderation")} className={`side-btn ${activeTab === "moderation" ? "active" : ""}`} style={styles.sideBtn}>
            Moderation History
          </button>
          <button onClick={() => setActiveTab("analytics")} className={`side-btn ${activeTab === "analytics" ? "active" : ""}`} style={styles.sideBtn}>
            Analytics
          </button>
        </nav>
      </aside>

      <main style={{ flex: 1 }}>
        <header style={styles.header}>
          <h1 style={styles.title}>Admin Control Center</h1>
          <p style={styles.subtitle}>
            Supervise user activities, manage moderation restrictions, and review classification statistics.
          </p>
        </header>

        {error && <div style={styles.error}>{error}</div>}

      {/* Overview: summary cards + recent activity */}
      {activeTab === "overview" && (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16, marginBottom: 20 }}>
            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: "var(--text)", fontWeight: 700 }}>Total Registered Users</div>
              <div style={{ fontSize: 22, fontWeight: 800 }}>{analytics?.total_users || 0}</div>
            </div>
            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: "var(--text)", fontWeight: 700 }}>Toxic Messages</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: "var(--status-toxic)" }}>{analytics?.toxic_messages || 0}</div>
            </div>
            <div className="card" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, color: "var(--text)", fontWeight: 700 }}>Overall Toxicity Rate</div>
              <div style={{ fontSize: 22, fontWeight: 800 }}>{analytics?.total_messages ? Math.round(((analytics.toxic_messages||0)/analytics.total_messages)*100) + '%' : '0%'}</div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 20, marginBottom: 20 }}>
            <div className="card" style={{ padding: 16 }}>
              <h3 style={styles.sectionTitle}>Recent Toxic Activity</h3>
              {flags.length === 0 ? (
                <p style={styles.emptyText}>No recent toxic messages.</p>
              ) : (
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>Message</th>
                      <th>Category</th>
                      <th>Confidence</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {flags.slice(0, 10).map((f) => (
                      <tr key={f.id}>
                        <td style={{ fontWeight: 600 }}>{f.username}</td>
                        <td style={{ fontStyle: "italic", color: "var(--status-toxic)" }}>{f.message}</td>
                        <td><span className="badge badge-toxic">{f.prediction}</span></td>
                        <td>{f.confidence}%</td>
                        <td>{f.created_at ? new Date(f.created_at).toLocaleString() : "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="card" style={{ padding: 16 }}>
              <h3 style={styles.sectionTitle}>Recent Moderation Actions</h3>
              {moderationActions.length === 0 ? (
                <p style={styles.emptyText}>No moderation activity found.</p>
              ) : (
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>User</th>
                      <th>Action</th>
                      <th>Source</th>
                      <th>Reason</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {moderationActions.slice(0, 12).map((m) => (
                      <tr key={m.id}>
                        <td style={{ fontWeight: 600 }}>{m.user}</td>
                        <td>{m.action_type}</td>
                        <td>{m.source}</td>
                        <td style={{ maxWidth: 160, wordBreak: "break-word" }}>{m.reason || "-"}</td>
                        <td>{m.created_at ? new Date(m.created_at).toLocaleString() : "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </>
      )}

      {/* Tab Area 1: User Manager */}
      {activeTab === "users" && (
        <div className="card" style={styles.tabCard}>
          <div style={{ padding: 12, borderBottom: "1px solid var(--border)", display: "flex", gap: 12, alignItems: "center" }}>
            <input placeholder="Search username or email..." value={usersSearch} onChange={(e)=>setUsersSearch(e.target.value)} style={{padding:8, flex:1}} />
            <select value={usersFilterStatus} onChange={(e)=>setUsersFilterStatus(e.target.value)} style={{padding:8}}>
              <option value="">All Status</option>
              <option value="ACTIVE">ACTIVE</option>
              <option value="RESTRICTED">RESTRICTED</option>
              <option value="BLOCKED">BLOCKED</option>
            </select>
            <select value={usersFilterRole} onChange={(e)=>setUsersFilterRole(e.target.value)} style={{padding:8}}>
              <option value="">All Roles</option>
              <option value="USER">USER</option>
              <option value="ADMIN">ADMIN</option>
            </select>
          </div>
          <table className="admin-table">
            <thead>
              <tr>
                <th>Registration Date</th>
                <th>Username</th>
                <th>Email Address</th>
                <th>Role</th>
                <th>Status</th>
                <th>Warnings</th>
                <th>Total Messages</th>
                <th>Toxic Messages</th>
                <th>Toxicity Rate</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users
                .filter(u=>{
                  const q = usersSearch.toLowerCase().trim();
                  if(q && !(u.username?.toLowerCase().includes(q) || u.email?.toLowerCase().includes(q))) return false;
                  if(usersFilterStatus && u.account_status !== usersFilterStatus) return false;
                  if(usersFilterRole && u.role !== usersFilterRole) return false;
                  return true;
                })
                .map((u) => (
                <tr key={u.id}>
                  <td>{u.created_at ? new Date(u.created_at).toLocaleDateString() : '-'}</td>
                  <td style={{ fontWeight: "600", color: "var(--text-h)" }}>{u.username}</td>
                  <td>{u.email}</td>
                  <td><span className="badge badge-neutral">{u.role}</span></td>
                  <td>
                    <span className={`badge ${u.account_status === "ACTIVE" ? "badge-safe" : u.account_status === "RESTRICTED" ? "badge-warn" : "badge-toxic"}`}>{u.account_status}</span>
                  </td>
                  <td>{u.warning_count ?? 0}</td>
                  <td>{u.total_messages ?? 0}</td>
                  <td>{u.toxic_msg_count ?? 0}</td>
                  <td>{u.toxicity_rate !== undefined ? `${u.toxicity_rate}%` : '-'}</td>
                  <td>
                    <div style={styles.actionsFlex}>
                      <button onClick={()=>handleViewDetails(u.id)} style={{padding:'6px 10px', borderRadius:6}}>View</button>
                      {u.account_status === "ACTIVE" && (
                        <>
                          <button onClick={() => handleRestrict(u.id)} style={styles.restrictBtn}>
                            Restrict
                          </button>
                          <button onClick={() => handleBlock(u.id)} style={styles.blockBtn}>
                            Block
                          </button>
                        </>
                      )}
                      {u.account_status === "RESTRICTED" && (
                        <button onClick={() => handleUnrestrict(u.id)} style={styles.unblockBtn}>
                          Restore
                        </button>
                      )}
                      {u.account_status === "BLOCKED" && (
                        <button onClick={() => handleUnblock(u.id)} style={styles.unblockBtn}>
                          Restore
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* User details modal (moved here to avoid JSX parsing issues) */}
      {selectedUserDetails && (
        <div style={styles.modalOverlay}>
          <div style={styles.modalCard}>
            <button style={styles.modalClose} onClick={()=>setSelectedUserDetails(null)}>Close</button>
            <h3>{selectedUserDetails.user.username} — {selectedUserDetails.user.role}</h3>
            <p>Email: {selectedUserDetails.user.email}</p>
            <p>Status: <strong>{selectedUserDetails.user.account_status}</strong></p>
            <p>Warnings: {selectedUserDetails.user.warning_count}</p>
            <div style={{display:'flex', gap:8, margin:'8px 0 16px 0'}}>
              {selectedUserDetails.user.account_status === 'ACTIVE' && (
                <>
                  <button onClick={()=>{ const mins = prompt('Restrict minutes','60'); if(!mins) return; const reason = prompt('Reason','Violation'); if(!reason) return; handleRestrict(selectedUserDetails.user.id); }} style={styles.restrictBtn}>Restrict</button>
                  <button onClick={()=>{ if(!confirm('Block this user?')) return; const reason = prompt('Reason','Severe violation'); if(!reason) return; handleBlock(selectedUserDetails.user.id); }} style={styles.blockBtn}>Block</button>
                </>
              )}
              {selectedUserDetails.user.account_status === 'RESTRICTED' && (
                <button onClick={()=>{ if(!confirm('Remove this chat restriction?')) return; handleUnrestrict(selectedUserDetails.user.id); }} style={styles.unblockBtn}>Restore</button>
              )}
              {selectedUserDetails.user.account_status === 'BLOCKED' && (
                <button onClick={()=>{ if(!confirm('Unblock this user?')) return; handleUnblock(selectedUserDetails.user.id); }} style={styles.unblockBtn}>Restore</button>
              )}
            </div>
            <h4>Chat Activity</h4>
            <p>Total messages: {selectedUserDetails.chat_history.length}</p>
            <div style={{maxHeight:200, overflow:'auto'}}>
              {selectedUserDetails.chat_history.map(c=> (
                <div key={c.id} style={{borderBottom:'1px solid var(--border)', padding:'6px 0'}}>
                  <div style={{fontStyle:'italic'}}>{c.message}</div>
                  <div style={{fontSize:12, color:'var(--text)'}}>{c.prediction} — {c.confidence}%</div>
                </div>
              ))}
            </div>
            <h4>Moderation History</h4>
            <div style={{maxHeight:200, overflow:'auto'}}>
              {selectedUserDetails.moderation_history.map(m=> (
                <div key={m.id} style={{borderBottom:'1px solid var(--border)', padding:'6px 0'}}>
                  <div>{m.action_type} — {m.reason}</div>
                  <div style={{fontSize:12, color:'var(--text)'}}>Source: {m.restriction_start ? 'ADMIN' : 'SYSTEM'} — {m.created_at}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tab Area 2: Flagged Chat messages logs */}
      {(activeTab === "flags" || activeTab === "chatAudit") && (
        <div className="card" style={styles.tabCard}>
          <div style={{padding:12, borderBottom:'1px solid var(--border)', display:'flex', gap:8, alignItems:'center'}}>
            <input placeholder="Search message or username..." value={flagsSearch} onChange={e=>setFlagsSearch(e.target.value)} style={{padding:8, flex:1}} />
            <select value={flagsFilterPrediction} onChange={e=>setFlagsFilterPrediction(e.target.value)} style={{padding:8}}>
              <option value="">All Categories</option>
              {[...new Set(flags.map(f=>f.prediction))].map(p=> <option key={p} value={p}>{p}</option>)}
            </select>
            <input type="date" value={flagsStartDate} onChange={e=>setFlagsStartDate(e.target.value)} style={{padding:8}} />
            <input type="date" value={flagsEndDate} onChange={e=>setFlagsEndDate(e.target.value)} style={{padding:8}} />
            <button onClick={()=>fetchFlags()} style={{padding:8}}>Apply</button>
          </div>

          {flags.length === 0 ? (
            <p style={styles.emptyText}>Zero flagged moderation messages found.</p>
          ) : (
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Violator User</th>
                  <th>Game</th>
                  <th>Room</th>
                  <th>Message</th>
                  <th>Category</th>
                  <th>Model / Confidence</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {flags.map((f) => (
                  <tr key={f.id}>
                    <td>{f.created_at ? new Date(f.created_at).toLocaleString() : '-'}</td>
                    <td style={{ fontWeight: "600", color: "var(--text-h)" }}>{f.username}</td>
                    <td>{f.game_name || '-'}</td>
                    <td>{f.room_name || '-'}</td>
                    <td style={{ fontStyle: "italic", color: "var(--status-toxic)" }}>
                      "{f.message}"
                    </td>
                    <td>
                      <span className="badge badge-toxic">{f.prediction}</span>
                    </td>
                    <td>
                      <div style={{fontWeight:600}}>{f.confidence}%</div>
                      <div style={{fontSize:12, color:'var(--text)'}}>{f.selected_model}</div>
                    </td>
                    <td>
                      <div style={styles.actionsFlex}>
                        {f.user_id && <button onClick={()=>handleViewDetails(f.user_id)} style={{padding:'6px 8px'}}>View User</button>}
                        {f.user_id && <button onClick={()=>handleRestrict(f.user_id)} style={styles.restrictBtn}>Restrict</button>}
                        {f.user_id && <button onClick={()=>{ if(confirm('Block this user?')) handleBlock(f.user_id); }} style={styles.blockBtn}>Block</button>}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Tab Area 3: Toxicity Analytics charts */}
      {activeTab === "analytics" && analytics && (
        <div style={styles.analyticsGrid}>
          {/* Circular/Summary Metrics card */}
          <div className="card glass" style={styles.analyticsSummary}>
            <h3 style={styles.sectionTitle}>Enforcement Analytics</h3>
            <div style={styles.metricItem}>
              <span style={styles.metricVal}>{analytics.total_messages}</span>
              <span style={styles.metricLabel}>Total Chat Messages scanned</span>
            </div>
            <div style={styles.metricItem}>
              <span style={{ ...styles.metricVal, color: "var(--status-toxic)" }}>
                {analytics.toxic_messages}
              </span>
              <span style={styles.metricLabel}>Flagged toxic messages</span>
            </div>
            <div style={styles.metricItem}>
              <span style={{ ...styles.metricVal, color: "var(--status-warn)" }}>
                {analytics.warnings_count}
              </span>
              <span style={styles.metricLabel}>Warning responses issued</span>
            </div>
            <div style={styles.metricItem}>
              <span style={styles.metricVal}>{analytics.active_restrictions}</span>
              <span style={styles.metricLabel}>Active Chat Restrictions</span>
            </div>
          </div>

          {/* Styled CSS Bar Chart for toxicity classes */}
          <div className="card glass" style={styles.analyticsBarChart}>
            <h3 style={styles.sectionTitle}>Toxicity Distribution by Category</h3>
            <div style={styles.barGraphFlex}>
              {Object.entries(analytics.toxicity_by_class).map(([className, scoreValue]) => {
                // Find percentage compared to maximum flag category, or total toxic
                const maxVal = Math.max(...Object.values(analytics.toxicity_by_class), 1);
                const percent = Math.round((scoreValue / maxVal) * 100);

                return (
                  <div key={className} style={styles.chartBarRow}>
                    <span style={styles.barLabel}>{className} ({scoreValue})</span>
                    <div style={styles.barTrack}>
                      <div
                        style={{
                          ...styles.barFill,
                          width: `${percent}%`,
                          backgroundColor:
                            scoreValue > 0 ? "var(--status-toxic)" : "var(--border)",
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {/* Tab Area 4: Moderation History */}
      {activeTab === "moderation" && (
        <div className="card" style={styles.tabCard}>
          <div style={{padding:12, borderBottom:'1px solid var(--border)', display:'flex', gap:8, alignItems:'center'}}>
            <input placeholder="Filter by username..." value={moderationFilterUser} onChange={e=>setModerationFilterUser(e.target.value)} style={{padding:8, flex:1}} />
            <select value={moderationLimit} onChange={e=>setModerationLimit(parseInt(e.target.value,10))} style={{padding:8}}>
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
            <button onClick={()=>fetchModeration({user_id: moderationFilterUser || undefined, limit: moderationLimit})} style={{padding:8}}>Apply</button>
            <button onClick={()=>fetchModeration()} style={{padding:8}}>Refresh</button>
          </div>

          {refreshing ? (
            <div style={styles.emptyText}>Loading moderation history...</div>
          ) : moderationActions.length === 0 ? (
            <p style={styles.emptyText}>No moderation history to display.</p>
          ) : (
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>User</th>
                  <th>Action</th>
                  <th>Source</th>
                  <th>Reason</th>
                  <th>Expires</th>
                </tr>
              </thead>
              <tbody>
                {moderationActions.map(m=> (
                  <tr key={m.id}>
                    <td>{m.created_at ? new Date(m.created_at).toLocaleString() : '-'}</td>
                    <td style={{fontWeight:600}}>{m.user || m.user_id || '-'}</td>
                    <td>{m.action_type}</td>
                    <td>{m.source || 'SYSTEM'}</td>
                    <td style={{maxWidth:200, wordBreak:'break-word'}}>{m.reason || '-'}</td>
                    <td>{m.expires_at ? new Date(m.expires_at).toLocaleString() : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </main>
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
  tabsRow: {
    display: "flex",
    gap: "10px",
    marginBottom: "20px",
    borderBottom: "1px solid var(--border)",
    paddingBottom: "10px",
  },
  tabBtn: {
    backgroundColor: "transparent",
    color: "var(--text)",
    padding: "10px 20px",
    fontSize: "14px",
    fontWeight: "600",
    borderRadius: "6px",
    ":hover": {
      backgroundColor: "var(--bg-input)",
    },
  },
  activeTabBtn: {
    backgroundColor: "var(--accent-bg)",
    color: "var(--accent-hover)",
    padding: "10px 20px",
    fontSize: "14px",
    fontWeight: "600",
    borderRadius: "6px",
    border: "1px solid rgba(168, 85, 247, 0.3)",
  },
  tabCard: {
    padding: 0,
    backgroundColor: "var(--bg-panel)",
    border: "1px solid var(--border)",
    overflowX: "auto",
  },
  emptyText: {
    padding: "48px",
    textAlign: "center",
    color: "var(--text)",
  },
  actionsFlex: {
    display: "flex",
    gap: "10px",
  },
  restrictBtn: {
    backgroundColor: "var(--status-warn-bg)",
    color: "var(--status-warn)",
    border: "1px solid rgba(245, 158, 11, 0.2)",
    padding: "6px 12px",
    borderRadius: "6px",
    fontSize: "12px",
    fontWeight: "600",
  },
  blockBtn: {
    backgroundColor: "var(--status-toxic-bg)",
    color: "var(--status-toxic)",
    border: "1px solid rgba(239, 68, 68, 0.2)",
    padding: "6px 12px",
    borderRadius: "6px",
    fontSize: "12px",
    fontWeight: "600",
  },
  unblockBtn: {
    backgroundColor: "var(--status-safe-bg)",
    color: "var(--status-safe)",
    border: "1px solid rgba(16, 185, 129, 0.2)",
    padding: "6px 12px",
    borderRadius: "6px",
    fontSize: "12px",
    fontWeight: "600",
  },
  analyticsGrid: {
    display: "grid",
    gridTemplateColumns: "1fr 1.6fr",
    gap: "24px",
    "@media(max-width: 1024px)": {
      gridTemplateColumns: "1fr",
    },
  },
  analyticsSummary: {
    padding: "24px",
    display: "flex",
    flexDirection: "column",
    gap: "20px",
  },
  sectionTitle: {
    color: "var(--text-h)",
    fontSize: "18px",
    fontWeight: "700",
    margin: "0 0 16px 0",
    borderBottom: "1px solid var(--border)",
    paddingBottom: "10px",
  },
  metricItem: {
    display: "flex",
    flexDirection: "column",
    alignItems: "flex-start",
  },
  metricVal: {
    fontSize: "28px",
    fontWeight: "800",
    color: "var(--text-h)",
  },
  metricLabel: {
    fontSize: "12px",
    color: "var(--text)",
    fontWeight: "600",
  },
  analyticsBarChart: {
    padding: "24px",
  },
  barGraphFlex: {
    display: "flex",
    flexDirection: "column",
    gap: "18px",
  },
  chartBarRow: {
    display: "flex",
    flexDirection: "column",
    gap: "6px",
    textAlign: "left",
  },
  barLabel: {
    fontSize: "13px",
    fontWeight: "600",
    color: "var(--text-h)",
    textTransform: "capitalize",
  },
  barTrack: {
    width: "100%",
    height: "12px",
    backgroundColor: "var(--bg-input)",
    borderRadius: "6px",
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: "6px",
    transition: "width 0.4s ease-out",
  },
  loading: {
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
    marginBottom: "20px",
    textAlign: "center",
  },
  modalOverlay: {
    position: 'fixed', top:0,left:0,right:0,bottom:0, backgroundColor:'rgba(0,0,0,0.5)', display:'flex', alignItems:'center', justifyContent:'center', zIndex:1200
  },
  modalCard: {
    backgroundColor:'var(--bg-panel)', padding:20, borderRadius:8, width:'720px', maxHeight:'80vh', overflow:'auto', border:'1px solid var(--border)'
  },
  modalClose: {
    position:'absolute', right:12, top:12, background:'transparent', border:0, color:'var(--text)'
  }
  ,
  sidebar: {
    width: 220,
    padding: 16,
    backgroundColor: 'var(--bg-panel)',
    border: '1px solid var(--border)',
    borderRadius: 8,
    height: 'fit-content'
  },
  sideBrand: {
    marginBottom: 12
  },
  sideNav: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8
  },
  sideBtn: {
    textAlign: 'left',
    padding: '10px 12px',
    borderRadius: 6,
    background: 'transparent',
    border: 'none',
    color: 'var(--text)',
    fontWeight: 700,
    cursor: 'pointer'
  }
};
export default AdminDashboard;