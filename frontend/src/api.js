const API_BASE = "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }

  return response.json();
}

export const api = {
  getAgents: () => request("/agents"),

  getBorrowers: () => request("/borrowers"),

  getCalls: () => request("/calls"),

  getMetrics: () => request("/metrics"),

  progressiveDial: (payload) =>
    request("/dial/progressive", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  predictiveDial: (payload) =>
    request("/dial/predictive", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  createAgents: (count) =>
    request("/agents/bulk", {
      method: "POST",
      body: JSON.stringify({ count }),
    }),

  createBorrowers: (count) =>
    request("/borrowers/bulk", {
      method: "POST",
      body: JSON.stringify({ count }),
    }),

  setProviderHealth: (provider, health) =>
    request(`/providers/${provider}/health`, {
      method: "POST",
      body: JSON.stringify({ health }),
    }),
};