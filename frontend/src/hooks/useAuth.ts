import { useCallback, useEffect, useState } from "react";

export function useAuth() {
  const [token, setToken] = useState<string | null>(
    () => localStorage.getItem("auth_token")
  );

  useEffect(() => {
    const handler = () => setToken(localStorage.getItem("auth_token"));
    window.addEventListener("storage", handler);
    return () => window.removeEventListener("storage", handler);
  }, []);

  const setAuthToken = useCallback((t: string) => {
    localStorage.setItem("auth_token", t);
    setToken(t);
  }, []);

  const clearAuthToken = useCallback(() => {
    localStorage.removeItem("auth_token");
    setToken(null);
  }, []);

  return { token, setAuthToken, clearAuthToken, isAuthed: !!token };
}
