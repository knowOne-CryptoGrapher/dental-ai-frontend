import axios from "axios";

export const API_BASE_URL =
  process.env.REACT_APP_API_URL || "https://api.frontdeskdentalai.com";

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  withCredentials: false,
  headers: {
    "Content-Type": "application/json",
  },
});

// Attach the JWT from localStorage on every request so authenticated
// endpoints (appointments, patients, etc.) receive the Authorization header.
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("dental_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Surface 401s as a clear console warning — helps diagnose session expiry.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      console.warn("api: 401 Unauthorized — token may be expired or missing");
    }
    return Promise.reject(error);
  }
);
