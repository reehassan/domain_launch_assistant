import axios from "axios";

// ---- Config ----------------------------------------------------------
// Build-time value from Vite's env handling — see frontend/.env.production.
// Falls back to localhost for local `npm run dev`, where no .env.production
// is loaded (Vite only applies .env.production during `vite build`/`--mode
// production`, not `vite dev`).
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1/";
const ACCESS_KEY = "dla_access";
const REFRESH_KEY = "dla_refresh";

// ---- Token storage helpers --------------------------------------------
// Decision: both tokens in localStorage. This is the throwaway test
// client (Day 2), not the final UI — simplicity over correctness here.
// Revisit (access in memory + silent refresh on mount) when the real
// frontend gets built later in the roadmap.
export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  setTokens: ({ access, refresh }) => {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

// ---- Axios instance ----------------------------------------------------
const client = axios.create({
  baseURL: BASE_URL,
  headers: { "Content-Type": "application/json" },
});

// Attach Authorization header to every request if we have an access token.
client.interceptors.request.use((config) => {
  const access = tokenStore.getAccess();
  if (access) {
    config.headers.Authorization = `Bearer ${access}`;
  }
  return config;
});

// ---- 401 handling: try one silent refresh, then give up ----------------
// Prevents parallel requests from all firing their own refresh calls.
let refreshPromise = null;
async function refreshAccessToken() {
  const refresh = tokenStore.getRefresh();
  if (!refresh) throw new Error("No refresh token available");
  if (!refreshPromise) {
    refreshPromise = axios
      .post(`${BASE_URL}auth/token/refresh/`, { refresh })
      .then(({ data }) => {
        tokenStore.setTokens({ access: data.access });
        return data.access;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    // Only attempt refresh once per request, and only on 401s that aren't
    // the login/refresh endpoints themselves (avoid infinite loop).
    const isAuthEndpoint =
      originalRequest.url?.includes("auth/login") ||
      originalRequest.url?.includes("auth/token/refresh");
    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !isAuthEndpoint
    ) {
      originalRequest._retry = true;
      try {
        const newAccess = await refreshAccessToken();
        originalRequest.headers.Authorization = `Bearer ${newAccess}`;
        return client(originalRequest);
      } catch (refreshError) {
        tokenStore.clear();
        return Promise.reject(refreshError);
      }
    }
    return Promise.reject(error);
  }
);

// ---- Error normalization -------------------------------------------------
// Backend's custom_exception_handler wraps DRF errors as:
//   { error: { code, message, details } }
// This helper pulls that out safely, with a fallback in case something
// (e.g. a 500, or a network failure) doesn't go through DRF's handler at
// all and therefore isn't wrapped.

export function parseApiError(error) {
  const data = error?.response?.data;
  if (data?.error) {
    return {
      code: data.error.code ?? "UNKNOWN_ERROR",
      message: data.error.message ?? "Something went wrong.",
      details: data.error.details ?? null,
    };
  }
  if (data?.detail) {
    return {
      code: "UNKNOWN_ERROR",
      message: data.detail,
      details: null,
    };
  }
  return {
    code: "UNKNOWN_ERROR",
    message: error?.message ?? "Something went wrong.",
    details: null,
  };
}

// ---- Auth-specific calls -------------------------------------------------
// Login response is { access, refresh, user } — LoginView uses a custom
// LoginSerializer (TokenObtainPairSerializer subclass) that injects
// data["user"] = UserSerializer(self.user).data on top of the usual
// token pair, so the extra GET auth/me/ round trip this used to make
// right after login was redundant (audit fix — Ticket 8). user here is
// the same shape UserSerializer/getMe() already return elsewhere.
export async function login({ username, password }) {
  const { data } = await client.post("auth/login/", { username, password });
  tokenStore.setTokens({ access: data.access, refresh: data.refresh });
  return data.user;
}


// Google sign-in doubles as registration server-side (see accounts/views.py
// GoogleAuthView) — response shape matches login()'s exactly, so it's a
// drop-in for anything already handling a normal login response.
export async function googleLogin(credential) {
  const { data } = await client.post("auth/google/", { credential });
  tokenStore.setTokens({ access: data.access, refresh: data.refresh });
  return data.user;
}

export async function register({ username, email, password, first_name, last_name }) {
  const { data } = await client.post("auth/register/", {
    username,
    email,
    password,
    first_name,
    last_name,
  });
  return data; // note: register does NOT log the user in — call login() after
}

export async function logout() {
  const refresh = tokenStore.getRefresh();
  try {
    if (refresh) {
      await client.post("auth/logout/", { refresh });
    }
  } finally {
    // Clear local tokens regardless of whether the blacklist call
    // succeeded — a failed logout call shouldn't leave the user stuck.
    tokenStore.clear();
  }
}

export async function getMe() {
  const { data } = await client.get("auth/me/");
  return data;
}

export default client;