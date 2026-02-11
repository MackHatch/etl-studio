"use client";

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { apiFetch } from "./api";

const STORAGE_TOKEN = "etl_studio_token";
const STORAGE_USER = "etl_studio_user";

export type User = {
  id: string;
  email: string;
  name: string;
  role: string;
  active_org_id?: string | null;
  active_org_role?: string | null;
};

type AuthState = {
  token: string | null;
  user: User | null;
  ready: boolean;
};

type AuthContextValue = AuthState & {
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  setTokenAndUser: (token: string, user: User) => void;
  refreshUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

function loadStored(): { token: string | null; user: User | null } {
  if (typeof window === "undefined") return { token: null, user: null };
  try {
    const token = localStorage.getItem(STORAGE_TOKEN);
    const userRaw = localStorage.getItem(STORAGE_USER);
    const user = userRaw ? (JSON.parse(userRaw) as User) : null;
    return { token, user };
  } catch {
    return { token: null, user: null };
  }
}

function saveStored(token: string | null, user: User | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(STORAGE_TOKEN, token);
  else localStorage.removeItem(STORAGE_TOKEN);
  if (user) localStorage.setItem(STORAGE_USER, JSON.stringify(user));
  else localStorage.removeItem(STORAGE_USER);
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null,
    user: null,
    ready: false,
  });

  useEffect(() => {
    const { token, user } = loadStored();
    setState({ token, user, ready: true });
  }, []);

  const setTokenAndUser = useCallback((token: string, user: User) => {
    saveStored(token, user);
    setState({ token, user, ready: true });
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const data = await apiFetch<{
      access_token: string;
      token_type: string;
      user: User;
    }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setTokenAndUser(data.access_token, data.user);
  }, [setTokenAndUser]);

  const logout = useCallback(() => {
    saveStored(null, null);
    setState({ token: null, user: null, ready: true });
  }, []);

  const value: AuthContextValue = {
    ...state,
    login,
    logout,
    setTokenAndUser,
  };

  return (
    <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
