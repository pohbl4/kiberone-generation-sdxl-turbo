"use client";

import { create } from "zustand";

type BaseImage = {
  id: string;
  url: string;
  placeholderSlot?: string;
};

type ResultItem = {
  id: string;
  url: string;
  relativeUrl?: string;
  seed?: number;
  quality: "fast" | "normal" | "high";
  degraded?: boolean;
  downloadToken?: string;
};

type JobStatus = "idle" | "queued" | "running" | "done" | "error" | "cancelled";

type State = {
  prompt: string;
  baseImage: BaseImage | null;
  results: ResultItem[];
  currentResult: ResultItem | null;
  jobStatus: JobStatus;
  jobMessage?: string;
  activeJobId: string | null;
  lastSketchDataUrl: string | null;
  lastCanvasDataUrl: string | null;
  clearSketchVersion: number;
  sessionId: string | null;
  setPrompt: (value: string) => void;
  setBaseImage: (image: BaseImage | null) => void;
  pushResult: (result: ResultItem) => void;
  setCurrentResult: (result: ResultItem | null) => void;
  setJobStatus: (status: JobStatus, message?: string) => void;
  resetHistory: () => void;
  setActiveJobId: (jobId: string | null) => void;
  removeLatestResult: () => void;
  setLastSketch: (sketchDataUrl: string | null, canvasDataUrl: string | null) => void;
  requestClearSketch: () => void;
  setSessionId: (sessionId: string | null) => void;
};

export const useAppStore = create<State>((set) => ({
  prompt: "",
  baseImage: null,
  results: [],
  currentResult: null,
  jobStatus: "idle",
  jobMessage: undefined,
  activeJobId: null,
  lastSketchDataUrl: null,
  lastCanvasDataUrl: null,
  clearSketchVersion: 0,
  sessionId: null,
  setPrompt: (value) => set({ prompt: value }),
  setBaseImage: (image) => set({ baseImage: image }),
  pushResult: (result) =>
    set((state) => {
      const filtered = state.results.filter((item) => item.id !== result.id);
      const history = [...filtered, result];
      const trimmed = history.slice(-5);
      return {
        results: trimmed,
        currentResult: result,
      };
    }),
  setCurrentResult: (result) => set({ currentResult: result }),
  setJobStatus: (status, message) => set({ jobStatus: status, jobMessage: message }),
  resetHistory: () =>
    set({
      results: [],
      currentResult: null,
      activeJobId: null,
      jobStatus: "idle",
      jobMessage: undefined,
      lastSketchDataUrl: null,
      lastCanvasDataUrl: null,
    }),
  setActiveJobId: (jobId) => set({ activeJobId: jobId }),
  removeLatestResult: () =>
    set((state) => {
      if (state.results.length === 0) {
        return state;
      }
      const updated = state.results.slice(0, -1);
      return {
        results: updated,
        currentResult: updated[updated.length - 1] ?? null,
      };
    }),
  setLastSketch: (sketchDataUrl, canvasDataUrl) =>
    set({
      lastSketchDataUrl: sketchDataUrl,
      lastCanvasDataUrl: canvasDataUrl,
    }),
  requestClearSketch: () =>
    set((state) => ({ clearSketchVersion: state.clearSketchVersion + 1 })),
  setSessionId: (sessionId) =>
    set((state) => (state.sessionId === sessionId ? state : { sessionId })),
}));
