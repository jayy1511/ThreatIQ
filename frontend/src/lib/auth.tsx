"use client";

/**
 * Central helpers for storing and clearing the auth token.
 * We store in BOTH localStorage (for client reads) and a cookie (for middleware).
 */

export function saveToken(token: string) {
  try {
    // Local storage (client side convenience)
    localStorage.setItem("token", token);
  } catch {}

  try {
    // Cookie so middleware can read it server-side
    // 7 days
    const maxAge = 60 * 60 * 24 * 7;
    document.cookie = `token=${encodeURIComponent(token)}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
  } catch {}
}

export function clearToken() {
  try {
    localStorage.removeItem("token");
  } catch {}

  try {
    // expire cookie immediately
    document.cookie = `token=; Path=/; Max-Age=0; SameSite=Lax`;
  } catch {}
}

export function getToken(): string | null {
  try {
    return localStorage.getItem("token");
  } catch {
    return null;
  }
}

export function isLoggedIn(): boolean {
  return !!getToken();
}
