"use client";

const TOKEN_KEY = "token";
const USER_EMAIL_KEY = "userEmail";

export function saveToken(token: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem(TOKEN_KEY, token);
    document.cookie = `${TOKEN_KEY}=${token}; path=/; SameSite=Lax`;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") {
    return null;
  }

  const fromStorage = localStorage.getItem(TOKEN_KEY);
  if (fromStorage) return fromStorage;

  const match = document.cookie.match(
    new RegExp("(^| )" + TOKEN_KEY + "=([^;]+)")
  );
  return match ? decodeURIComponent(match[2]) : null;
}

export function clearToken() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
    document.cookie = `${TOKEN_KEY}=; Max-Age=0; path=/; SameSite=Lax`;
  }
}

export function saveUser(email: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem(USER_EMAIL_KEY, email);
  }
}

export function getUser(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  return localStorage.getItem(USER_EMAIL_KEY);
}

/**
 * Old code in sidebar uses this name.
 */
export function getUserEmail(): string | null {
  return getUser();
}

/**
 * Old dashboard code imports isLoggedIn – keep it working.
 */
export function isLoggedIn(): boolean {
  return !!getToken();
}
