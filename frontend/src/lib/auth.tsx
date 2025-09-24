"use client";

import { jwtDecode } from "jwt-decode";

/**
 * Central helpers for storing and clearing the auth token.
 * We store in BOTH localStorage (for client reads) and a cookie (for middleware).
 */

export function saveToken(token: string) {
  try {
    localStorage.setItem("token", token);
  } catch {}

  try {
    const maxAge = 60 * 60 * 24 * 7; // 7 days
    document.cookie = `token=${encodeURIComponent(
      token
    )}; Path=/; Max-Age=${maxAge}; SameSite=Lax`;
  } catch {}
}

export function clearToken() {
  try {
    localStorage.removeItem("token");
  } catch {}

  try {
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

/* ----------------- USER EMAIL HELPERS ----------------- */

export function saveUser(email: string) {
  try {
    localStorage.setItem("email", email);
  } catch {}
}

export function getUserEmail(): string | null {
  try {
    // Try from localStorage first
    const stored = localStorage.getItem("email");
    if (stored) return stored;

    // Try decode from token if email exists in payload
    const token = getToken();
    if (token) {
      try {
        const decoded: any = jwtDecode(token);
        return decoded.email || null;
      } catch {
        return null;
      }
    }

    return null;
  } catch {
    return null;
  }
}

export function clearUser() {
  try {
    localStorage.removeItem("email");
  } catch {}
}
