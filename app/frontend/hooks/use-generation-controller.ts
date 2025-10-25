"use client";

import { useCallback, useEffect, useMemo, useRef } from "react";

import { useTranslation } from "../providers/localization-provider";
import { useAppStore } from "../store/app-store";
import { API_BASE, API_BASE_RAW, WS_BASE_RAW } from "../lib/api-config";
import { redirectIfUnauthorized } from "../lib/auth-redirect";

type Quality = "fast" | "normal" | "high";

type PendingGeneration = {
  sketchDataUrl: string;
  canvasDataUrl: string | null;
  quality: Quality;
  seed?: number | null;
};

function normalizeWsBase(raw: string): string | null {
  try {
    const url = new URL(raw);
    url.search = "";
    url.hash = "";
    const trimmedPath = url.pathname.replace(/\/+$/, "");
    url.pathname = `${trimmedPath || ""}/`;
    return url.toString();
  } catch (error) {
    console.warn("Failed to normalize WS base", error);
    return null;
  }
}

function resolveWsBase(): string | null {
  if (WS_BASE_RAW) {
    const normalized = normalizeWsBase(WS_BASE_RAW);
    if (normalized) {
      return normalized;
    }
  }

  try {
    const apiUrl = new URL(API_BASE_RAW);
    const protocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${apiUrl.host}/ws/`;
  } catch (error) {
    console.warn("Failed to derive WS base from API", error);
  }

  if (typeof window !== "undefined" && window.location?.origin) {
    try {
      return new URL("/ws/", window.location.origin).toString();
    } catch (error) {
      console.warn("Failed to derive WS base from window origin", error);
    }
  }

  return null;
}

function deriveWsUrl(sessionId?: string | null): string | null {
  if (!sessionId) {
    return null;
  }

  const base = resolveWsBase();
  if (!base) {
    return null;
  }

  try {
    const url = new URL(base);
    url.searchParams.set("sid", sessionId);
    return url.toString();
  } catch (error) {
    console.warn("Failed to attach session id to WS url", error);
    const separator = base.includes("?") ? "&" : "?";
    const trimmed = base.endsWith("/") ? base : `${base}/`;
    return `${trimmed}${separator}sid=${encodeURIComponent(sessionId)}`;
  }
}

function getApiOrigin(): string | null {
  if (!API_BASE_RAW) {
    if (typeof window !== "undefined") {
      return window.location.origin;
    }
    return null;
  }
  try {
    const url = new URL(API_BASE_RAW);
    return `${url.protocol}//${url.host}`;
  } catch (error) {
    console.warn("Failed to derive API origin", error);
    if (typeof window !== "undefined") {
      return window.location.origin;
    }
    return API_BASE_RAW.replace(/\/?api$/, "");
  }
}

async function dataUrlToBlob(dataUrl: string): Promise<Blob> {
  const parts = dataUrl.split(",", 2);
  if (parts.length !== 2) {
    throw new Error("Invalid data URL");
  }
  const header = parts[0];
  const payload = parts[1];
  const mimeMatch = /data:(.*?);base64/.exec(header);
  const mime = mimeMatch && mimeMatch[1] ? mimeMatch[1] : "application/octet-stream";
  const binaryString = atob(payload);
  const length = binaryString.length;
  const bytes = new Uint8Array(length);
  for (let i = 0; i < length; i += 1) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return new Blob([bytes], { type: mime });
}

export function useGenerationController() {
  const { t, language } = useTranslation();
  const baseImage = useAppStore((state) => state.baseImage);
  const prompt = useAppStore((state) => state.prompt);
  const pushResult = useAppStore((state) => state.pushResult);
  const setJobStatus = useAppStore((state) => state.setJobStatus);
  const setCurrentResult = useAppStore((state) => state.setCurrentResult);
  const setBaseImage = useAppStore((state) => state.setBaseImage);
  const jobStatus = useAppStore((state) => state.jobStatus);
  const jobMessage = useAppStore((state) => state.jobMessage);
  const activeJobId = useAppStore((state) => state.activeJobId);
  const setActiveJobId = useAppStore((state) => state.setActiveJobId);
  const removeLatestResult = useAppStore((state) => state.removeLatestResult);
  const lastSketchDataUrl = useAppStore((state) => state.lastSketchDataUrl);
  const lastCanvasDataUrl = useAppStore((state) => state.lastCanvasDataUrl);
  const setLastSketch = useAppStore((state) => state.setLastSketch);
  const currentResult = useAppStore((state) => state.currentResult);
  const results = useAppStore((state) => state.results);
  const requestClearSketch = useAppStore((state) => state.requestClearSketch);
  const sessionId = useAppStore((state) => state.sessionId);

  const wsRef = useRef<WebSocket | null>(null);
  const pendingJobRef = useRef<string | null>(null);
  const pendingGenerationRef = useRef<PendingGeneration | null>(null);
  const cancellationRequestedRef = useRef(false);
  const lastJobStatusRef = useRef(jobStatus);

  const apiOrigin = useMemo(() => getApiOrigin(), []);

  const wsUrl = useMemo(() => deriveWsUrl(sessionId), [sessionId]);

  useEffect(() => {
    if (!wsUrl) {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      return;
    }

    let cancelled = false;
    let retryTimer: number | null = null;

    const connect = () => {
      if (cancelled) {
        return;
      }

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        const store = useAppStore.getState();
        const jobId = store.activeJobId;
        if (jobId) {
          const payload: Record<string, unknown> = {
            action: "subscribe",
            job_id: jobId,
          };
          if (typeof store.sessionId === "string" && store.sessionId.length > 0) {
            payload.sid = store.sessionId;
          }
          ws.send(JSON.stringify(payload));
        }
      };

      ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message.type === "status") {
            const status = message.value as "queued" | "running" | string;
            if (status === "queued" || status === "running") {
              setJobStatus(status);
            }
          } else if (message.type === "result") {
            const relativeUrl = typeof message.result_url === "string" ? message.result_url : "";
            const absoluteUrl = relativeUrl.startsWith("http")
              ? relativeUrl
              : apiOrigin
              ? `${apiOrigin}${relativeUrl}`
              : relativeUrl;
            pushResult({
              id: message.job_id,
              url: absoluteUrl,
              relativeUrl,
              seed: message.seed ?? undefined,
              quality: (message.quality_effective as Quality | undefined) ?? "normal",
              degraded: Boolean(message.quality_degraded),
              downloadToken: message.download_token ?? undefined,
            });
            setJobStatus("done");
            setActiveJobId(null);
            pendingJobRef.current = null;
          } else if (message.type === "error") {
            setJobStatus("error", message.message);
            setActiveJobId(null);
            pendingJobRef.current = null;
          } else if (message.type === "cancelled") {
            setJobStatus("cancelled");
            setActiveJobId(null);
            pendingJobRef.current = null;
          }
        } catch (error) {
          console.error("Failed to parse WS message", error);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onclose = () => {
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        if (!cancelled) {
          retryTimer = window.setTimeout(connect, 3000);
        }
      };
    };

    connect();

    return () => {
      cancelled = true;
      if (retryTimer !== null) {
        window.clearTimeout(retryTimer);
      }
      const current = wsRef.current;
      if (current) {
        wsRef.current = null;
        current.close();
      }
    };
  }, [apiOrigin, pushResult, setActiveJobId, setJobStatus, wsUrl]);

  useEffect(() => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return;
    }
    if (activeJobId && pendingJobRef.current !== activeJobId) {
      const payload: Record<string, unknown> = {
        action: "subscribe",
        job_id: activeJobId,
      };
      const sid = useAppStore.getState().sessionId;
      if (typeof sid === "string" && sid.length > 0) {
        payload.sid = sid;
      }
      ws.send(JSON.stringify(payload));
      pendingJobRef.current = activeJobId;
    }
  }, [activeJobId]);

  const buildApiUrl = useCallback((path: string) => {
    if (!API_BASE) {
      return path;
    }
    const normalized = path.startsWith("/") ? path : `/${path}`;
    return `${API_BASE}${normalized}`;
  }, []);

  const executeGeneration = useCallback(
    async ({ sketchDataUrl, canvasDataUrl, quality, seed }: PendingGeneration) => {
      if (!baseImage) {
        setJobStatus("error", t("ui.errors.base_required"));
        return;
      }
      try {
        const [sketchBlob, canvasBlob] = await Promise.all([
          dataUrlToBlob(sketchDataUrl),
          canvasDataUrl ? dataUrlToBlob(canvasDataUrl) : Promise.resolve<Blob | null>(null),
        ]);
        const formData = new FormData();
        formData.append("base_image_id", baseImage.id);
        formData.append("prompt", prompt);
        formData.append("ui_language", language);
        formData.append("quality", quality);
        if (typeof seed === "number") {
          formData.append("seed", String(seed));
        }
        formData.append("sketch_png", sketchBlob, "sketch.png");
        if (canvasBlob) {
          formData.append("canvas_png", canvasBlob, "canvas.png");
        }

        setJobStatus("queued");
        setLastSketch(sketchDataUrl, canvasDataUrl);

        const response = await fetch(buildApiUrl("/generate"), {
          method: "POST",
          body: formData,
          credentials: "include",
        });

        if (redirectIfUnauthorized(response)) {
          setJobStatus("idle");
          setActiveJobId(null);
          pendingJobRef.current = null;
          pendingGenerationRef.current = null;
          cancellationRequestedRef.current = false;
          return;
        }

        if (!response.ok) {
          const errorData = await response.json().catch(() => null);
          const message = errorData?.error?.message ?? "Generation failed";
          setJobStatus("error", message);
          setActiveJobId(null);
          pendingJobRef.current = null;
          return;
        }

        const data = await response.json();
        if (data?.status === "skipped") {
          setJobStatus("idle");
          setActiveJobId(null);
          pendingJobRef.current = null;
          return;
        }
        setActiveJobId(data.job_id ?? null);
        if (data.quality_degraded) {
          setJobStatus("queued");
        }
      } catch (error) {
        setJobStatus("error", (error as Error).message);
        setActiveJobId(null);
        pendingJobRef.current = null;
      }
    },
    [baseImage, buildApiUrl, language, prompt, setActiveJobId, setJobStatus, setLastSketch, t],
  );

  const requestCancellation = useCallback(async () => {
    if (!activeJobId || cancellationRequestedRef.current) {
      return;
    }
    cancellationRequestedRef.current = true;
    try {
      const response = await fetch(buildApiUrl("/generate/cancel"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ job_id: activeJobId }),
      });

      if (redirectIfUnauthorized(response)) {
        setJobStatus("idle");
        setActiveJobId(null);
        pendingJobRef.current = null;
        pendingGenerationRef.current = null;
        cancellationRequestedRef.current = false;
        return;
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        const message = errorData?.error?.message ?? "Cancel failed";
        setJobStatus("error", message);
        pendingGenerationRef.current = null;
        cancellationRequestedRef.current = false;
      }
    } catch (error) {
      setJobStatus("error", (error as Error).message);
      pendingGenerationRef.current = null;
      cancellationRequestedRef.current = false;
    }
  }, [activeJobId, buildApiUrl, setActiveJobId, setJobStatus]);

  const submitGeneration = useCallback(
    async (
      sketchDataUrl: string,
      canvasDataUrl?: string | null,
      quality: Quality = "normal",
      seed?: number | null,
    ) => {
      if (!sketchDataUrl) {
        return;
      }
      if (!baseImage) {
        setJobStatus("error", t("ui.errors.base_required"));
        return;
      }

      const payload: PendingGeneration = {
        sketchDataUrl,
        canvasDataUrl: canvasDataUrl ?? null,
        quality,
        seed: typeof seed === "number" ? seed : null,
      };

      if (jobStatus === "queued" || jobStatus === "running") {
        pendingGenerationRef.current = payload;
        void requestCancellation();
        return;
      }

      pendingGenerationRef.current = null;
      await executeGeneration(payload);
    },
    [
      activeJobId,
      baseImage,
      executeGeneration,
      jobStatus,
      requestCancellation,
      setActiveJobId,
      setJobStatus,
      t,
    ],
  );

  useEffect(() => {
    const previous = lastJobStatusRef.current;
    lastJobStatusRef.current = jobStatus;
    const wasGenerating = previous === "queued" || previous === "running";
    const isGenerating = jobStatus === "queued" || jobStatus === "running";
    if (!isGenerating) {
      cancellationRequestedRef.current = false;
    }
    if (wasGenerating && !isGenerating) {
      const pending = pendingGenerationRef.current;
      if (pending) {
        pendingGenerationRef.current = null;
        void executeGeneration(pending);
      }
    }
  }, [executeGeneration, jobStatus]);

  useEffect(() => {
    if (!pendingGenerationRef.current) {
      return;
    }
    if (!activeJobId) {
      return;
    }
    if (jobStatus !== "queued" && jobStatus !== "running") {
      return;
    }
    void requestCancellation();
  }, [activeJobId, jobStatus, requestCancellation]);

  useEffect(() => {
    if (!activeJobId) {
      return;
    }
    if (jobStatus !== "queued" && jobStatus !== "running") {
      return;
    }

    let cancelled = false;

    const poll = async () => {
      if (cancelled) {
        return;
      }

      const ws = wsRef.current;
      if (ws && ws.readyState === WebSocket.OPEN) {
        return;
      }

      try {
        const response = await fetch(buildApiUrl(`/generate/status/${activeJobId}`), {
          credentials: "include",
        });

        if (redirectIfUnauthorized(response)) {
          setJobStatus("idle");
          setActiveJobId(null);
          pendingJobRef.current = null;
          pendingGenerationRef.current = null;
          cancellationRequestedRef.current = false;
          return;
        }

        if (!response.ok) {
          return;
        }

        const data = await response.json().catch(() => null);
        if (!data || data.job_id !== activeJobId) {
          return;
        }

        const status = data.status as string | undefined;
        if (status === "done" && typeof data.result_url === "string") {
          const relativeUrl = data.result_url;
          const absoluteUrl = relativeUrl.startsWith("http")
            ? relativeUrl
            : apiOrigin
            ? `${apiOrigin}${relativeUrl}`
            : relativeUrl;
          pushResult({
            id: data.job_id,
            url: absoluteUrl,
            relativeUrl,
            seed: typeof data.seed === "number" ? data.seed : undefined,
            quality: (data.quality_effective as Quality | undefined) ?? "normal",
            degraded: Boolean(data.quality_degraded),
            downloadToken: typeof data.download_token === "string" ? data.download_token : undefined,
          });
          setJobStatus("done");
          setActiveJobId(null);
          pendingJobRef.current = null;
          return;
        }

        if (status === "error") {
          const message =
            typeof data.error_message === "string" && data.error_message.length > 0
              ? data.error_message
              : "Generation failed";
          setJobStatus("error", message);
          setActiveJobId(null);
          pendingJobRef.current = null;
          return;
        }

        if (status === "cancelled") {
          setJobStatus("cancelled");
          setActiveJobId(null);
          pendingJobRef.current = null;
          return;
        }

        if (status === "queued" || status === "running") {
          setJobStatus(status);
        }
      } catch (error) {
        console.warn("Polling job status failed", error);
      }
    };

    void poll();
    const timer = window.setInterval(() => {
      void poll();
    }, 3000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeJobId, apiOrigin, buildApiUrl, jobStatus, pushResult, setActiveJobId, setJobStatus]);

  const regenerate = useCallback(async () => {
    if (!lastSketchDataUrl) {
      return;
    }
    await submitGeneration(lastSketchDataUrl, lastCanvasDataUrl, "normal");
  }, [lastCanvasDataUrl, lastSketchDataUrl, submitGeneration]);

  const improve = useCallback(async () => {
    if (!lastSketchDataUrl || !currentResult?.seed) {
      return;
    }
    await submitGeneration(lastSketchDataUrl, lastCanvasDataUrl, "high", currentResult.seed);
  }, [currentResult?.seed, lastCanvasDataUrl, lastSketchDataUrl, submitGeneration]);

  const undo = useCallback(async () => {
    try {
      const response = await fetch(buildApiUrl("/history/undo"), {
        method: "POST",
        credentials: "include",
      });
      if (redirectIfUnauthorized(response)) {
        setJobStatus("idle");
        return;
      }

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        const message = data?.error?.message ?? "Undo failed";
        setJobStatus("error", message);
        return;
      }
      const data = await response.json();
      removeLatestResult();
      const updatedResults = useAppStore.getState().results;
      const next = updatedResults.find((item) => item.id === data.result_id) ?? updatedResults[updatedResults.length - 1] ?? null;
      setCurrentResult(next);
      setJobStatus("done");
    } catch (error) {
      setJobStatus("error", (error as Error).message);
    }
  }, [buildApiUrl, removeLatestResult, setCurrentResult, setJobStatus]);

  const applyResultToCanvas = useCallback(async () => {
    if (!currentResult) {
      return;
    }
    try {
      const response = await fetch(buildApiUrl("/canvas/apply-result"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ result_url: currentResult.url }),
      });
      if (redirectIfUnauthorized(response)) {
        setJobStatus("idle");
        return;
      }

      if (!response.ok) {
        const data = await response.json().catch(() => null);
        const message = data?.error?.message ?? "Apply failed";
        setJobStatus("error", message);
        return;
      }
      const data = await response.json();
      setBaseImage({ id: data.image_id, url: data.url });
      requestClearSketch();
      setJobStatus("idle");
    } catch (error) {
      setJobStatus("error", (error as Error).message);
    }
  }, [buildApiUrl, currentResult, requestClearSketch, setBaseImage, setJobStatus]);

  const downloadCurrent = useCallback(() => {
    if (!currentResult?.downloadToken || !apiOrigin) {
      return;
    }
    const baseUrl = currentResult.relativeUrl ?? currentResult.url;
    const absolute = baseUrl.startsWith("http") ? baseUrl : `${apiOrigin}${baseUrl}`;
    const separator = absolute.includes("?") ? "&" : "?";
    const url = `${absolute}${separator}t=${currentResult.downloadToken}`;
    window.open(url, "_blank", "noopener");
  }, [apiOrigin, currentResult]);

  const selectHistoryItem = useCallback(
    (resultId: string) => {
      const next = results.find((item) => item.id === resultId);
      if (next) {
        setCurrentResult(next);
      }
    },
    [results, setCurrentResult],
  );

  const isGenerating = jobStatus === "queued" || jobStatus === "running";

  return {
    submitGeneration,
    regenerate,
    improve,
    undo,
    applyResultToCanvas,
    downloadCurrent,
    selectHistoryItem,
    isGenerating,
    jobStatus,
    jobMessage,
    currentResult,
  };
}
