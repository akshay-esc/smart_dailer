import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  Bot,
  Phone,
  Users,
  ShieldCheck,
  RefreshCw,
  Play,
  Server,
  CheckCircle,
  AlertCircle,
  Radio,
  Clock3,
} from "lucide-react";
import { api } from "./api";

const initialMetrics = {
  agents_total: 0,
  agents_available: 0,
  agents_connected: 0,
  agent_utilization_pct: 0,
  calls_total: 0,
  calls_initiated_or_beyond: 0,
  calls_completed: 0,
  calls_failed: 0,
  borrowers_queued: 0,
  provider_health: {},
};

function StatCard({ title, value, icon: Icon, description }) {
  return (
    <div className="stat-card">
      <div className="stat-top">
        <span>{title}</span>
        <Icon size={20} />
      </div>

      <div className="stat-value">{value}</div>

      <div className="stat-description">{description}</div>
    </div>
  );
}

function StatusBadge({ status }) {
  const normalized = String(status || "UNKNOWN").toUpperCase();

  return (
    <span className={`badge badge-${normalized.toLowerCase()}`}>
      <span className="badge-dot" />
      {normalized.replaceAll("_", " ")}
    </span>
  );
}

function App() {
  const [metrics, setMetrics] = useState(initialMetrics);
  const [agents, setAgents] = useState([]);
  const [calls, setCalls] = useState([]);
  const [provider, setProvider] = useState("fast");
  const [maxCalls, setMaxCalls] = useState(5);
  const [mode, setMode] = useState("progressive");
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [lastResult, setLastResult] = useState(null);

  const loadData = useCallback(async (showSpinner = false) => {
    if (showSpinner) setRefreshing(true);

    try {
      const [metricsData, agentsData, callsData] = await Promise.all([
        api.getMetrics(),
        api.getAgents(),
        api.getCalls(),
      ]);

      setMetrics(metricsData);
      setAgents(agentsData);
      setCalls(callsData);
      setError("");
    } catch (err) {
      setError(
        `Could not load backend data: ${err.message}. Make sure FastAPI is running on port 8000.`
      );
    } finally {
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();

    const interval = setInterval(() => loadData(), 5000);

    return () => clearInterval(interval);
  }, [loadData]);

  async function runDialer() {
    setLoading(true);
    setMessage("");
    setError("");
    setLastResult(null);

    try {
      const payload = {
        campaign_id: "campaign-001",
        provider,
      };

      if (mode === "progressive") {
        payload.max_calls = Number(maxCalls);
      } else {
        payload.max_requested = Number(maxCalls);
      }

      const result =
        mode === "progressive"
          ? await api.progressiveDial(payload)
          : await api.predictiveDial(payload);

      setLastResult(result);
      setMessage(
        `${mode === "progressive" ? "Progressive" : "Predictive"} dialing finished. ` +
          `${result.created} call(s) initiated; Safety Controller approved ${result.safety_approved}.`
      );

      await loadData();
    } catch (err) {
      setError(`Dialing failed: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  async function toggleProvider(providerName) {
    setError("");
    setMessage("");

    try {
      const current = metrics.provider_health?.[providerName] || "healthy";
      const next = current === "healthy" ? "unhealthy" : "healthy";

      await api.setProviderHealth(providerName, next);

      setMessage(`${providerName} provider is now ${next}.`);
      await loadData();
    } catch (err) {
      setError(`Could not update provider: ${err.message}`);
    }
  }

  async function createDemoData() {
    setLoading(true);
    setError("");
    setMessage("");

    try {
      await api.createAgents(5);
      await api.createBorrowers(20);

      setMessage("Created 5 agents and 20 borrowers.");
      await loadData();
    } catch (err) {
      setError(`Could not create demo data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  const initiatedCalls = calls.filter((call) =>
    ["INITIATED", "RINGING", "ANSWERED", "CONNECTED"].includes(call.status)
  ).length;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Radio size={23} />
          </div>

          <div>
            <h2>SmartDialer</h2>
            <span>Collections platform</span>
          </div>
        </div>

        <div className="sidebar-label">WORKSPACE</div>

        <div className="nav-item active">
          <Activity size={18} />
          Overview
        </div>

        <div className="nav-item">
          <Users size={18} />
          Agents
        </div>

        <div className="nav-item">
          <Phone size={18} />
          Call monitoring
        </div>

        <div className="nav-item">
          <ShieldCheck size={18} />
          Safety controller
        </div>

        <div className="sidebar-bottom">
          <div className="connection-indicator">
            <span className="online-dot" />
            API connection
          </div>

          <small>FastAPI · Local environment</small>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <div className="breadcrumb">Workspace / Overview</div>
            <h1>SmartDialer Dashboard</h1>
            <p>Monitor agent utilization, dialing activity, and call safety.</p>
          </div>

          <button
            className="button button-secondary"
            onClick={() => loadData(true)}
            disabled={refreshing}
          >
            <RefreshCw size={16} className={refreshing ? "spin" : ""} />
            Refresh
          </button>
        </header>

        {error && (
          <div className="alert alert-error">
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        )}

        {message && (
          <div className="alert alert-success">
            <CheckCircle size={18} />
            <span>{message}</span>
          </div>
        )}

        <section className="section-heading">
          <div>
            <h2>System overview</h2>
            <p>Current operational metrics</p>
          </div>

          <span className="live-label">
            <span className="online-dot" />
            Auto-refresh every 5 seconds
          </span>
        </section>

        <section className="stats-grid">
          <StatCard
            title="Total agents"
            value={metrics.agents_total}
            icon={Users}
            description={`${metrics.agents_available} currently available`}
          />

          <StatCard
            title="Agent utilization"
            value={`${metrics.agent_utilization_pct}%`}
            icon={Activity}
            description={`${metrics.agents_connected} connected agents`}
          />

          <StatCard
            title="Total calls"
            value={metrics.calls_total}
            icon={Phone}
            description={`${initiatedCalls} currently in progress`}
          />

          <StatCard
            title="Queued borrowers"
            value={metrics.borrowers_queued}
            icon={Clock3}
            description="Waiting to be called"
          />
        </section>

        <section className="content-grid">
          <div className="panel dialer-panel">
            <div className="panel-heading">
              <div className="heading-icon purple">
                <Bot size={20} />
              </div>

              <div>
                <h2>Dialer controls</h2>
                <p>Configure and run a dialing operation.</p>
              </div>
            </div>

            <label htmlFor="dialing-mode">Dialing mode</label>

            <div className="mode-selector">
              <button
                className={mode === "progressive" ? "mode active-mode" : "mode"}
                onClick={() => setMode("progressive")}
              >
                <Phone size={17} />
                Progressive
              </button>

              <button
                className={mode === "predictive" ? "mode active-mode" : "mode"}
                onClick={() => setMode("predictive")}
              >
                <Activity size={17} />
                Predictive
              </button>
            </div>

            <label htmlFor="provider">Telecom provider</label>

            <select
              id="provider"
              value={provider}
              onChange={(event) => setProvider(event.target.value)}
            >
              <option value="fast">Fast Mock Provider</option>
              <option value="flaky">Flaky Mock Provider</option>
            </select>

            <label htmlFor="maxCalls">Maximum requested calls</label>

            <input
              id="maxCalls"
              type="number"
              min="1"
              max="1000"
              value={maxCalls}
              onChange={(event) => setMaxCalls(event.target.value)}
            />

            <div className="helper-text">
              The Safety Controller independently limits calls to available
              capacity.
            </div>

            <button
              className="button button-primary run-button"
              onClick={runDialer}
              disabled={loading || Number(maxCalls) < 1}
            >
              <Play size={17} />
              {loading
                ? "Processing..."
                : mode === "progressive"
                  ? "Run Progressive Dialing"
                  : "Run Predictive Dialing"}
            </button>

            <button
              className="button button-secondary run-button"
              onClick={createDemoData}
              disabled={loading}
            >
              <Users size={17} />
              Create Demo Data
            </button>

            {lastResult && (
              <div className="decision-box">
                <div className="decision-title">
                  <ShieldCheck size={18} />
                  Safety Controller decision
                </div>

                <div className="decision-row">
                  <span>Requested</span>
                  <strong>{lastResult.requested}</strong>
                </div>

                <div className="decision-row">
                  <span>Approved</span>
                  <strong>{lastResult.safety_approved}</strong>
                </div>

                <div className="decision-row">
                  <span>Created</span>
                  <strong>{lastResult.created}</strong>
                </div>

                <div className="decision-reason">
                  {lastResult.safety_reason}
                </div>

                {lastResult.pacing && (
                  <pre className="pacing-details">
                    {JSON.stringify(lastResult.pacing, null, 2)}
                  </pre>
                )}
              </div>
            )}
          </div>

          <div className="panel">
            <div className="panel-heading">
              <div className="heading-icon green">
                <ShieldCheck size={20} />
              </div>

              <div>
                <h2>Provider health</h2>
                <p>Mock telecom provider status</p>
              </div>
            </div>

            {["fast", "flaky"].map((providerName) => {
              const health =
                metrics.provider_health?.[providerName] || "unknown";

              return (
                <div className="provider-row" key={providerName}>
                  <div className="provider-info">
                    <div className="provider-icon">
                      <Server size={19} />
                    </div>

                    <div>
                      <strong>
                        {providerName === "fast"
                          ? "Fast Provider"
                          : "Flaky Provider"}
                      </strong>

                      <span>
                        {providerName === "fast"
                          ? "Low latency · Reliable"
                          : "Simulated failures · Delays"}
                      </span>
                    </div>
                  </div>

                  <div className="provider-actions">
                    <StatusBadge status={health} />

                    <button
                      className="text-button"
                      onClick={() => toggleProvider(providerName)}
                    >
                      Toggle
                    </button>
                  </div>
                </div>
              );
            })}

            <div className="provider-note">
              <AlertCircle size={17} />
              The flaky provider can simulate failed initiation requests. This
              dashboard does not place real telephone calls.
            </div>

            <div className="mini-stats">
              <div>
                <span>Completed calls</span>
                <strong>{metrics.calls_completed}</strong>
              </div>

              <div>
                <span>Failed calls</span>
                <strong>{metrics.calls_failed}</strong>
              </div>
            </div>
          </div>
        </section>

        <section className="panel table-panel">
          <div className="panel-heading table-heading">
            <div>
              <h2>Agent monitoring</h2>
              <p>Live view of agent allocation states</p>
            </div>

            <span className="table-count">{agents.length} agents</span>
          </div>

          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Agent ID</th>
                  <th>Name</th>
                  <th>Status</th>
                  <th>Reserved call</th>
                </tr>
              </thead>

              <tbody>
                {agents.length === 0 ? (
                  <tr>
                    <td colSpan="4" className="empty-state">
                      No agents found. Use Create Demo Data to get started.
                    </td>
                  </tr>
                ) : (
                  agents.slice(0, 10).map((agent) => (
                    <tr key={agent.id}>
                      <td>AGT-{String(agent.id).padStart(3, "0")}</td>
                      <td>{agent.name}</td>
                      <td>
                        <StatusBadge status={agent.status} />
                      </td>
                      <td>{agent.reserved_call_id || "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel table-panel">
          <div className="panel-heading table-heading">
            <div>
              <h2>Recent calls</h2>
              <p>Latest call lifecycle updates</p>
            </div>

            <span className="table-count">{calls.length} calls</span>
          </div>

          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Call ID</th>
                  <th>Agent ID</th>
                  <th>Borrower ID</th>
                  <th>Provider</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {calls.length === 0 ? (
                  <tr>
                    <td colSpan="5" className="empty-state">
                      No calls yet. Run a dialing operation to get started.
                    </td>
                  </tr>
                ) : (
                  calls.slice(0, 10).map((call) => (
                    <tr key={call.id}>
                      <td className="call-id">{call.id}</td>
                      <td>{call.agent_id}</td>
                      <td>{call.borrower_id}</td>
                      <td>{call.provider}</td>
                      <td>
                        <StatusBadge status={call.status} />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>

        <footer className="footer">
          <span>SmartDialer · Technical Assignment Prototype</span>
          <span>React + FastAPI</span>
        </footer>
      </main>
    </div>
  );
}

export default App;