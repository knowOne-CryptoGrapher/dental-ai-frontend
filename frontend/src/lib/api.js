const API_BASE = import.meta.env.VITE_API_URL || process.env.REACT_APP_API_URL;

export async function api(path, options = {}) {
  const url = `${API_BASE}${path}`;

  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    },
    ...options
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(error || "API request failed");
  }

  return response.json();
}

export default api;
