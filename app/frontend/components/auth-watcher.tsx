"use client";

import { useEffect } from "react";

import { API_BASE } from "../lib/api-config";
import { useAppStore } from "../store/app-store";
import { redirectToLogin } from "../lib/auth-redirect";

const CHECK_INTERVAL_MS = 60_000;
const REFRESH_THROTTLE_MS = 15_000;

function buildAuthUrl(path: string): string {
  try {
    return `${API_BASE.replace(/\/$/, "")}${path}`;
  } catch (error) {
    console.warn("Failed to build auth URL", error);
    return `/api${path}`;
  }
}

export default function AuthWatcher() {
  const setSessionId = useAppStore((state) => state.setSessionId);
  useEffect(() => {
    let cancelled = false;
    const authUrl = buildAuthUrl("/auth/me");
    const refreshUrl = buildAuthUrl("/auth/refresh");
    let lastRefresh = 0;

    const sendRefresh = async () => {
      const now = Date.now();
      if (now - lastRefresh < REFRESH_THROTTLE_MS) {
        return;
      }
      lastRefresh = now;
      try {
        await fetch(refreshUrl, { method: "POST", credentials: "include" });
      } catch (error) {
        console.warn("Failed to refresh auth session", error);
      }
    };

    const check = async () => {
      try {
        const response = await fetch(authUrl, { credentials: "include" });
        if (cancelled) {
          return;
        }
        if (response.status === 401) {
          setSessionId(null);
          redirectToLogin();
          return;
        }
        if (response.ok) {
          try {
            const data = await response.json();
            if (data && typeof data.sid === "string") {
              setSessionId(data.sid);
            }
          } catch (error) {
            console.warn("Failed to parse auth payload", error);
          }
        }
      } catch (error) {
        console.warn("Auth check failed", error);
      }
    };

    void check();
    const timer = window.setInterval(check, CHECK_INTERVAL_MS);

    const handleInteraction = (event: Event) => {
      if (!(event.target instanceof Element)) {
        return;
      }
      const isButton = Boolean(event.target.closest("button"));
      if (!isButton) {
        return;
      }
      void sendRefresh();
    };

    window.addEventListener("pointerdown", handleInteraction, { passive: true });

    const teardown = () => {
      cancelled = true;
      window.clearInterval(timer);
      window.removeEventListener("pointerdown", handleInteraction);
    };

    return teardown;
  }, [setSessionId]);

  return null;
}
