import axios from "axios";

export const API_BASE_URL = "https://api.frontdeskdentalai.com";

export const api = axios.create({
  baseURL: `${API_BASE_URL}/api`,
  withCredentials: false,
  headers: {
    "Content-Type": "application/json",
  },
});
