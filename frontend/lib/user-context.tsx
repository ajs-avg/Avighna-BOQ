"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { getMe, isApiError } from "./api";
import { clearSession, getStoredProfile, getToken, redirectToLogin, storeProfile } from "./auth";
import type { Role, UserProfile } from "./types";

export interface UserContextValue {
  profile: UserProfile | null;
  loading: boolean;
  error: string | null;
  /** Re-fetch /api/v1/me. */
  refresh: () => Promise<void>;
  /** Replace the cached profile (e.g. after set-password). */
  setProfile: (profile: UserProfile) => void;
  logout: () => void;
  hasRole: (...roles: Role[]) => boolean;
  isAdmin: boolean;
  canApprove: boolean;
}

const UserContext = createContext<UserContextValue | null>(null);

export function UserProvider({ children }: { children: ReactNode }) {
  // Start empty on both server and client (avoids a hydration mismatch); the cached
  // profile is restored in an effect so the shell can paint before /me resolves.
  const [profile, setProfileState] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const cached = getStoredProfile();
    if (cached) setProfileState((current) => current ?? cached);
  }, []);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      redirectToLogin();
      return;
    }
    try {
      const me = await getMe();
      setProfileState(me);
      storeProfile(me);
      setError(null);
    } catch (err) {
      if (isApiError(err) && err.status === 401) return; // api.ts already redirected
      setError(err instanceof Error ? err.message : "Could not load your profile");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setProfile = useCallback((p: UserProfile) => {
    setProfileState(p);
    storeProfile(p);
  }, []);

  const logout = useCallback(() => {
    clearSession();
    window.location.assign("/login");
  }, []);

  const value = useMemo<UserContextValue>(() => {
    const role = profile?.role;
    return {
      profile,
      loading,
      error,
      refresh,
      setProfile,
      logout,
      hasRole: (...roles: Role[]) => (role ? roles.includes(role) : false),
      isAdmin: role === "admin",
      canApprove: role === "admin" || role === "reviewer",
    };
  }, [profile, loading, error, refresh, setProfile, logout]);

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used inside <UserProvider>");
  return ctx;
}
