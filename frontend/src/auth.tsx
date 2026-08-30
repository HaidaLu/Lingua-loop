import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, setAuthToken, setUnauthorizedHandler } from "./api";

interface AuthCtx {
  token: string | null;
  email: string | null;
  ready: boolean;
  registered: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const Ctx = createContext<AuthCtx | null>(null);

const TOKEN_KEY = "ll_token";
const EMAIL_KEY = "ll_email";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY));
  const [email, setEmail] = useState<string | null>(() => localStorage.getItem(EMAIL_KEY));
  const [registered, setRegistered] = useState(true);
  const [ready, setReady] = useState(false);

  const apply = useCallback((t: string | null, e: string | null) => {
    setToken(t);
    setEmail(e);
    setAuthToken(t);
    if (t) {
      localStorage.setItem(TOKEN_KEY, t);
      localStorage.setItem(EMAIL_KEY, e ?? "");
    } else {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(EMAIL_KEY);
    }
  }, []);

  const logout = useCallback(() => apply(null, null), [apply]);

  useEffect(() => {
    setAuthToken(token);
    setUnauthorizedHandler(() => apply(null, null));
  }, [token, apply]);

  // on startup: check whether an account exists + validate any stored token
  useEffect(() => {
    (async () => {
      try {
        const s = await api.authStatus();
        setRegistered(s.registered);
      } catch {
        /* backend not up; the login page will surface the error */
      }
      const saved = localStorage.getItem(TOKEN_KEY);
      if (saved) {
        try {
          const me = await api.me();
          apply(me.access_token, me.email);
        } catch {
          apply(null, null);
        }
      }
      setReady(true);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = useCallback(
    async (e: string, p: string) => {
      const r = await api.login(e, p);
      apply(r.access_token, r.email);
    },
    [apply],
  );

  const register = useCallback(
    async (e: string, p: string) => {
      const r = await api.register(e, p);
      setRegistered(true);
      apply(r.access_token, r.email);
    },
    [apply],
  );

  const value = useMemo<AuthCtx>(
    () => ({ token, email, ready, registered, login, register, logout }),
    [token, email, ready, registered, login, register, logout],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth must be used inside AuthProvider");
  return v;
}
