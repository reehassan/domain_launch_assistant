import { createContext, useContext, useEffect, useState } from "react";
import * as auth from "../api/client";
import { tokenStore } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true); // true while we check for an existing session

  // On mount: if a token already exists (page refresh), try to hydrate
  // the user from /me/ instead of forcing a re-login every reload.
  useEffect(() => {
    const access = tokenStore.getAccess();
    if (!access) {
      setLoading(false);
      return;
    }
    auth
      .getMe()
      .then(setUser)
      .catch(() => {
        // Token invalid/expired and refresh failed somewhere upstream —
        // clear everything so the app doesn't think we're logged in.
        tokenStore.clear();
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  async function doLogin(credentials) {
    const loggedInUser = await auth.login(credentials);
    setUser(loggedInUser);
    return loggedInUser;
  }

  async function doRegister(payload) {
    // register() does NOT log the user in (no tokens in its response) —
    // caller is responsible for redirecting to /login after this resolves.
    return auth.register(payload);
  }

  async function doLogout() {
    await auth.logout();
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, loading, login: doLogin, register: doRegister, logout: doLogout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
}
