"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "../../../providers/localization-provider";
import { API_BASE } from "../../../lib/api-config";

export default function LoginPage() {
  const router = useRouter();
  const { t } = useTranslation();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ password })
      });

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        if (data?.error?.code === "INVALID_CREDENTIALS") {
          setError(t("ui.errors.invalid_credentials"));
          return;
        }

        if (response.status === 404) {
          setError(t("ui.errors.api_unreachable"));
          return;
        }

        setError(data?.error?.message ?? t("ui.errors.generic"));
        return;
      }

      router.push("/app");
    } catch (err) {
      setError(t("ui.errors.network"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4">
      <form onSubmit={handleSubmit} className="w-full max-w-md space-y-6 rounded-[28px] border border-border bg-surface p-8 shadow-[0_16px_48px_rgba(0,0,0,0.35)]">
        <h1 className="text-3xl font-semibold text-text-primary">{t("ui.login.title")}</h1>
        <p className="text-base font-semibold text-text-primary">{t("ui.login.username_hint")}</p>
        <label className="block text-sm font-medium text-text-muted">
          {t("ui.login.password")}
          <input
            type="password"
            className="mt-2 w-full rounded-xl border border-border/60 bg-surface-muted/70 px-3 py-2 text-text-primary focus:border-brand"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="current-password"
          />
        </label>
        {error ? <p className="text-sm text-red-400" role="alert">{error}</p> : null}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-xl bg-brand px-4 py-3 text-base font-semibold text-background transition hover:bg-brand-dark disabled:opacity-50"
        >
          {loading ? "..." : t("ui.login.submit")}
        </button>
      </form>
    </div>
  );
}
