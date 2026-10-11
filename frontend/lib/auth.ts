import { PROFILE_KEY, TOKEN_COOKIE, TOKEN_KEY } from "./constants";
import type { UserProfile } from "./types";

/**
 * Local-account session storage: JWT + profile in localStorage and a
 * `avighna_token` cookie so `middleware.ts` can guard routes on the edge.
 */

const isBrowser = () => typeof window !== "undefined";

export function getToken(): string | null {
  if (!isBrowser()) return null;
  try {
    return window.localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function getStoredProfile(): UserProfile | null {
  if (!isBrowser()) return null;
  try {
    const raw = window.localStorage.getItem(PROFILE_KEY);
    return raw ? (JSON.parse(raw) as UserProfile) : null;
  } catch {
    return null;
  }
}

export function storeProfile(profile: UserProfile): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
  } catch {
    // storage may be unavailable (private mode); the API remains the source of truth
  }
}

export function setSession(token: string, profile: UserProfile, expiresInSeconds: number): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(TOKEN_KEY, token);
    window.localStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
  } catch {
    // ignore
  }
  const maxAge = Math.max(60, Math.floor(expiresInSeconds || 0) || 60 * 60 * 12);
  const secure = window.location.protocol === "https:" ? "; Secure" : "";
  document.cookie = `${TOKEN_COOKIE}=${encodeURIComponent(token)}; Path=/; Max-Age=${maxAge}; SameSite=Lax${secure}`;
}

export function clearSession(): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.removeItem(TOKEN_KEY);
    window.localStorage.removeItem(PROFILE_KEY);
  } catch {
    // ignore
  }
  document.cookie = `${TOKEN_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax`;
}

/** Clear the session and send the browser to /login (optionally remembering where it was). */
export function redirectToLogin(remember = true): void {
  if (!isBrowser()) return;
  clearSession();
  const here = window.location.pathname + window.location.search;
  const next = remember && here !== "/" && !here.startsWith("/login") ? `?next=${encodeURIComponent(here)}` : "";
  window.location.assign(`/login${next}`);
}

/** Sanitise a `?next=` value so we only ever redirect inside the app. */
export function safeNext(value: string | null | undefined): string {
  if (!value) return "/";
  if (!value.startsWith("/") || value.startsWith("//")) return "/";
  if (value.startsWith("/login") || value.startsWith("/set-password")) return "/";
  return value;
}
