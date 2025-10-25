"use client";

import Image from "next/image";
import {
  ChangeEvent,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { Stage, Layer, Line, Image as KonvaImage } from "react-konva";
import useImage from "use-image";
import { useTranslation } from "../providers/localization-provider";
import { useAppStore } from "../store/app-store";
import { useGenerationController } from "../hooks/use-generation-controller";
import { API_BASE, API_BASE_RAW } from "../lib/api-config";
import { redirectIfUnauthorized } from "../lib/auth-redirect";

const CANVAS_SIZE = 448;
const CANVAS_VIEWPORT = 448;
const COLORS = ["#FFFFFF", "#0F0A09", "#F4B740", "#EF6F6C", "#B99CFF", "#6ED6B9", "#FFCE73", "#9AC9FF"];
const CONTROL_LABEL_CLASS = "text-xs font-semibold uppercase tracking-[0.32em] text-text-subtle";

const TEMPLATE_SLOTS = [
  {
    id: "template-mountains",
    labelKey: "ui.canvas.templates.mountains" as const,
    preview: "/assets/pattern1.png"
  },
  {
    id: "template-city",
    labelKey: "ui.canvas.templates.city" as const,
    preview: "/assets/pattern2.png"
  },
  {
    id: "template-lab",
    labelKey: "ui.canvas.templates.lab" as const,
    preview: "/assets/pattern3.png"
  },
  {
    id: "template-forest",
    labelKey: "ui.canvas.templates.forest" as const,
    preview: "/assets/pattern4.png"
  }
];

async function fetchTemplateDataUrl(path: string): Promise<string> {
  const response = await fetch(path, { credentials: "include" });
  if (!response.ok) {
    throw new Error(`Failed to load template asset: ${response.status}`);
  }
  const blob = await response.blob();
  return await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      if (typeof reader.result === "string") {
        resolve(reader.result);
      } else {
        reject(new Error("Template reader returned empty result"));
      }
    };
    reader.onerror = () => reject(new Error("Failed to read template asset"));
    reader.readAsDataURL(blob);
  });
}

type Stroke = {
  tool: "brush" | "eraser";
  points: number[];
  color: string;
  size: number;
};

type PaletteToggleProps = {
  label: string;
  active: boolean;
  onClick: () => void;
};

type PaletteActionProps = {
  icon: string;
  label: string;
  onClick: () => void;
  disabled?: boolean;
  fullWidth?: boolean;
};

const PaletteToggle = ({ label, active, onClick }: PaletteToggleProps) => (
  <button
    type="button"
    onClick={onClick}
    aria-pressed={active}
    className={`flex flex-1 items-center justify-center gap-2 rounded-2xl border px-4 py-2 text-sm font-semibold transition ${
      active
        ? "border-brand bg-brand text-brand-contrast shadow-[0_16px_36px_rgba(244,183,64,0.35)]"
        : "border-white/10 bg-[#2F2727] text-text-muted hover:border-brand/60 hover:text-text-primary"
    }`}
  >
    {label}
  </button>
);

const PaletteAction = ({ icon, label, onClick, disabled, fullWidth }: PaletteActionProps) => (
  <button
    type="button"
    onClick={onClick}
    disabled={disabled}
    className={`flex items-center justify-center gap-2 rounded-2xl border border-white/10 bg-[#2F2727] px-4 py-2 text-sm font-medium text-text-primary transition hover:border-brand/60 hover:text-brand disabled:cursor-not-allowed disabled:opacity-60 ${
      fullWidth ? "w-full" : ""
    }`}
  >
    <Image src={icon} alt="" width={16} height={16} aria-hidden className="opacity-80" />
    {label}
  </button>
);

export default function CanvasPanel() {
  const { t } = useTranslation();
  const baseImage = useAppStore((state) => state.baseImage);
  const setBaseImage = useAppStore((state) => state.setBaseImage);
  const resetHistory = useAppStore((state) => state.resetHistory);
  const clearSketchVersion = useAppStore((state) => state.clearSketchVersion);
  const prompt = useAppStore((state) => state.prompt);
  const stageRef = useRef<any>(null);
  const sketchLayerRef = useRef<any>(null);
  const generationTimerRef = useRef<number | null>(null);
  const didDrawRef = useRef(false);
  const initialTemplateAppliedRef = useRef(false);
  const lastPromptRef = useRef<string>("");
  const [tool, setTool] = useState<"brush" | "eraser">("brush");
  const [color, setColor] = useState<string>(COLORS[0]);
  const [strokeWidth, setStrokeWidth] = useState<number>(12);
  const [isDrawing, setIsDrawing] = useState(false);
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const [selectedTemplate, setSelectedTemplate] = useState<string | null>(null);
  const canvasContainerRef = useRef<HTMLDivElement | null>(null);
  const [viewportSize, setViewportSize] = useState<number>(CANVAS_VIEWPORT);
  const { submitGeneration } = useGenerationController();

  const apiBase = API_BASE;
  const apiOrigin = useMemo(() => {
    if (!apiBase) return "";
    try {
      const url = new URL(API_BASE_RAW);
      return url.origin;
    } catch {
      return "";
    }
  }, [apiBase]);

  const baseImageUrl = useMemo(() => {
    if (!baseImage) return null;
    if (baseImage.url) {
      if (baseImage.url.startsWith("http")) {
        return baseImage.url;
      }
      if (apiOrigin) {
        return `${apiOrigin}${baseImage.url}`;
      }
      return baseImage.url;
    }

    if (baseImage.placeholderSlot) {
      const template = TEMPLATE_SLOTS.find((item) => item.id === baseImage.placeholderSlot);
      if (template?.preview) {
        return template.preview;
      }
    }

    return null;
  }, [apiOrigin, baseImage]);

  const [baseLayerImage] = useImage(baseImageUrl ?? "", "use-credentials");

  useEffect(() => {
    const container = canvasContainerRef.current;
    if (!container || typeof window === "undefined") {
      return;
    }

    const updateViewport = () => {
      const width = container.clientWidth || CANVAS_VIEWPORT;
      const size = Math.min(width, CANVAS_VIEWPORT);
      setViewportSize(size);
    };

    updateViewport();

    const Observer = window.ResizeObserver;
    if (Observer) {
      const observer = new Observer(() => updateViewport());
      observer.observe(container);
      return () => observer.disconnect();
    }

    window.addEventListener("resize", updateViewport);
    return () => window.removeEventListener("resize", updateViewport);
  }, []);

  useEffect(() => {
    if (!baseImage) {
      setSelectedTemplate(null);
      return;
    }

    if (baseImage.placeholderSlot) {
      setSelectedTemplate(baseImage.placeholderSlot);
    } else {
      setSelectedTemplate(null);
    }
  }, [baseImage]);

  const handleUpload = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const file = event.target.files?.[0];
      if (!file) return;

      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch(`${apiBase}/upload`, {
          method: "POST",
          body: formData,
          credentials: "include"
        });

        if (redirectIfUnauthorized(response)) {
          return;
        }

        if (!response.ok) {
          return;
        }

        const data = await response.json();
        setBaseImage({ id: data.image_id, url: data.url });
        setSelectedTemplate(null);
        resetHistory();
        setStrokes([]);
      } catch (error) {
        console.error(error);
      }
    },
    [apiBase, resetHistory, setBaseImage]
  );

  const handleTemplateSelect = useCallback(
    async (templateId: string) => {
      const template = TEMPLATE_SLOTS.find((item) => item.id === templateId);
      if (!template) {
        return;
      }

      let imageData: string | null = null;
      try {
        imageData = await fetchTemplateDataUrl(template.preview);
      } catch (error) {
        console.warn("Failed to load template locally", error);
      }

      try {
        const response = await fetch(`${apiBase}/canvas/select-template`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(
            imageData
              ? { template_id: templateId, image_data: imageData }
              : { template_id: templateId }
          )
        });
        if (redirectIfUnauthorized(response)) {
          return;
        }

        if (!response.ok) {
          return;
        }
        const data = await response.json();
        setBaseImage({ id: data.image_id, url: data.url, placeholderSlot: templateId });
        setSelectedTemplate(templateId);
        resetHistory();
        setStrokes([]);
      } catch (error) {
        console.error(error);
      }
    },
    [apiBase, resetHistory, setBaseImage]
  );

  useEffect(() => {
    if (initialTemplateAppliedRef.current) {
      return;
    }

    if (baseImage) {
      initialTemplateAppliedRef.current = true;
      return;
    }

    if (!selectedTemplate) {
      initialTemplateAppliedRef.current = true;
      void handleTemplateSelect(TEMPLATE_SLOTS[0].id);
    }
  }, [baseImage, handleTemplateSelect, selectedTemplate]);

  const clampToCanvas = useCallback((value: number) => {
    if (value < 0) return 0;
    if (value > CANVAS_SIZE) return CANVAS_SIZE;
    return value;
  }, []);

  const getPointerPosition = useCallback(
    (event: any) => {
      const stage = stageRef.current;
      if (!stage) {
        return null;
      }

      const container = typeof stage.container === "function" ? stage.container() : null;
      if (!container) {
        return null;
      }

      const rect = container.getBoundingClientRect();
      const evt = event?.evt as PointerEvent | TouchEvent | undefined;
      const point =
        evt && "clientX" in evt
          ? { x: evt.clientX, y: evt.clientY }
          : evt && "touches" in evt && evt.touches[0]
          ? { x: evt.touches[0].clientX, y: evt.touches[0].clientY }
          : null;

      if (!point) {
        return null;
      }

      const scale = rect.width > 0 ? CANVAS_SIZE / rect.width : 1;
      const x = clampToCanvas((point.x - rect.left) * scale);
      const y = clampToCanvas((point.y - rect.top) * scale);

      return { x, y };
    },
    [clampToCanvas]
  );

  const scheduleGeneration = useCallback(async () => {
    if (generationTimerRef.current) {
      window.clearTimeout(generationTimerRef.current);
    }

    generationTimerRef.current = window.setTimeout(async () => {
      const stage = stageRef.current;
      try {
        const sketchCanvas: HTMLCanvasElement | undefined = sketchLayerRef.current?.toCanvas?.({
          pixelRatio: 1
        });
        if (!sketchCanvas) {
          return;
        }

        const sketchDataUrl = sketchCanvas.toDataURL("image/png");
        let canvasDataUrl: string | null = null;

        if (stage) {
          canvasDataUrl = stage.toDataURL({ mimeType: "image/png", pixelRatio: 1 });
        }

        await submitGeneration(sketchDataUrl, canvasDataUrl, "normal");
      } catch (error) {
        console.warn("Failed to capture full canvas snapshot", error);
      } finally {
        generationTimerRef.current = null;
      }
    }, 120);
  }, [submitGeneration]);

  const finishStroke = useCallback(async () => {
    if (!isDrawing) return;
    setIsDrawing(false);

    if (!didDrawRef.current) {
      setStrokes((prev) => prev.slice(0, -1));
      return;
    }

    await scheduleGeneration();
  }, [isDrawing, scheduleGeneration]);

  const handlePointerDown = useCallback(
    (event: any) => {
      event.evt.preventDefault();
      const position = getPointerPosition(event);
      if (!position) return;

      didDrawRef.current = false;
      const newStroke: Stroke = {
        tool,
        points: [position.x, position.y],
        color,
        size: strokeWidth
      };

      setStrokes((prev) => {
        const next = [...prev, newStroke];
        if (next.length > 50) {
          return next.slice(next.length - 50);
        }
        return next;
      });
      setIsDrawing(true);
    },
    [color, getPointerPosition, strokeWidth, tool]
  );

  const handlePointerMove = useCallback(
    (event: any) => {
      if (!isDrawing) return;
      const position = getPointerPosition(event);
      if (!position) return;

      didDrawRef.current = true;
      setStrokes((prev) => {
        if (prev.length === 0) {
          return prev;
        }

        const updated = [...prev];
        const lastStroke = updated[updated.length - 1];
        if (!lastStroke || !Array.isArray(lastStroke.points)) {
          return prev;
        }

        updated[updated.length - 1] = {
          ...lastStroke,
          points: [...lastStroke.points, position.x, position.y]
        };

        return updated;
      });
    },
    [getPointerPosition, isDrawing]
  );

  const handlePointerUp = useCallback(() => {
    finishStroke();
  }, [finishStroke]);

  const clearSketch = useCallback(() => {
    setStrokes([]);
  }, []);

  useEffect(() => {
    clearSketch();
  }, [clearSketch, clearSketchVersion]);

  useEffect(() => {
    return () => {
      if (generationTimerRef.current) {
        window.clearTimeout(generationTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const handleWindowPointerUp = () => {
      if (isDrawing) {
        finishStroke();
      }
    };

    window.addEventListener("pointerup", handleWindowPointerUp);
    window.addEventListener("pointercancel", handleWindowPointerUp);

    return () => {
      window.removeEventListener("pointerup", handleWindowPointerUp);
      window.removeEventListener("pointercancel", handleWindowPointerUp);
    };
  }, [finishStroke, isDrawing]);

  useEffect(() => {
    const trimmed = prompt.trim();
    if (lastPromptRef.current === trimmed) {
      return;
    }

    lastPromptRef.current = trimmed;

    if (!baseImage || trimmed.length === 0) {
      return;
    }

    void scheduleGeneration();
  }, [baseImage, prompt, scheduleGeneration]);

  const hasStrokes = strokes.length > 0;

  return (
    <section className="rounded-[40px] border border-white/10 bg-surface px-8 py-8 shadow-panel">
      <div className="flex flex-col gap-6">
        <h2 className="text-2xl font-semibold text-white">{t("ui.canvas.title")}</h2>

        <div className="flex flex-col gap-6 xl:flex-row">
          <div className="flex flex-1 flex-col gap-6">
            <div className="rounded-[36px] bg-[#2F2727] p-6">
              <div className="flex flex-col items-center gap-6">
                <div
                  ref={canvasContainerRef}
                  className="relative mx-auto flex aspect-square w-full max-w-[448px] items-center justify-center overflow-hidden rounded-2xl bg-[#1B1412]"
                >
                  <Stage
                    ref={stageRef}
                    width={CANVAS_SIZE}
                    height={CANVAS_SIZE}
                    onMouseDown={handlePointerDown}
                    onMouseMove={handlePointerMove}
                    onMouseUp={handlePointerUp}
                    onMouseLeave={handlePointerUp}
                    onTouchStart={handlePointerDown}
                    onTouchMove={handlePointerMove}
                    onTouchEnd={handlePointerUp}
                    onTouchCancel={handlePointerUp}
                    style={{
                      width: viewportSize,
                      height: viewportSize,
                      touchAction: "none"
                    }}
                  >
                    <Layer listening={false}>
                      {baseLayerImage ? (
                        <KonvaImage image={baseLayerImage} width={CANVAS_SIZE} height={CANVAS_SIZE} listening={false} />
                      ) : null}
                    </Layer>
                    <Layer ref={sketchLayerRef}>
                      {strokes.map((stroke, index) => (
                        <Line
                          key={`${stroke.tool}-${index}`}
                          points={stroke.points}
                          stroke={stroke.tool === "eraser" ? "#000000" : stroke.color}
                          strokeWidth={stroke.size}
                          lineCap="round"
                          lineJoin="round"
                          globalCompositeOperation={stroke.tool === "eraser" ? "destination-out" : "source-over"}
                        />
                      ))}
                    </Layer>
                  </Stage>
                </div>
                <div className="mx-auto w-full max-w-[448px] rounded-[28px] bg-[#352C2A] p-5">
                  <div className="flex flex-col gap-5">
                    <div className="flex flex-col gap-2 sm:flex-row">
                      <PaletteToggle
                        label={t("ui.canvas.brush")}
                        active={tool === "brush"}
                        onClick={() => setTool("brush")}
                      />
                      <PaletteToggle
                        label={t("ui.canvas.eraser")}
                        active={tool === "eraser"}
                        onClick={() => setTool("eraser")}
                      />
                    </div>

                    <div className="flex flex-col items-center gap-3">
                      <span className={CONTROL_LABEL_CLASS}>
                        {t("ui.canvas.thickness")}
                      </span>
                      <div className="w-full rounded-2xl bg-[#2F2727] px-3 py-2">
                        <input
                          type="range"
                          min={1}
                          max={64}
                          value={strokeWidth}
                          onChange={(event) => setStrokeWidth(Number(event.target.value))}
                          aria-label={t("ui.canvas.thickness")}
                          className="accent-brand w-full"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col items-center gap-3">
                      <span className={CONTROL_LABEL_CLASS}>
                        {t("ui.canvas.color")}
                      </span>
                      <div className="mx-auto grid grid-cols-4 gap-3 place-items-center">
                        {COLORS.map((currentColor) => (
                          <button
                            key={currentColor}
                            type="button"
                            className={`h-9 w-9 rounded-full border-[3px] transition ${
                              color === currentColor
                                ? "border-brand shadow-[0_12px_28px_rgba(244,183,64,0.35)]"
                                : "border-white/10 hover:border-brand/40"
                            }`}
                            style={{ backgroundColor: currentColor }}
                            onClick={() => setColor(currentColor)}
                            aria-label={`${t("ui.canvas.color")} ${currentColor}`}
                          />
                        ))}
                      </div>
                    </div>

                    <div>
                      <PaletteAction
                        icon="/assets/icons/eraser.svg"
                        label={t("ui.canvas.clear")}
                        onClick={clearSketch}
                        disabled={!hasStrokes}
                        fullWidth
                      />
                    </div>
                    <div className="space-y-4">
                      <div className="flex flex-wrap justify-center gap-4">
                        {TEMPLATE_SLOTS.map((template) => (
                          <button
                            key={template.id}
                            type="button"
                            onClick={() => handleTemplateSelect(template.id)}
                            className={`flex h-20 w-20 items-center justify-center overflow-hidden rounded-2xl border transition ${
                              selectedTemplate === template.id
                                ? "border-brand bg-brand/5"
                                : "border-white/10 bg-[#2F2727] hover:border-brand/60"
                            }`}
                            aria-pressed={selectedTemplate === template.id}
                          >
                            <Image
                              src={template.preview}
                              alt={t(template.labelKey)}
                              width={80}
                              height={80}
                              className="h-full w-full object-cover"
                            />
                          </button>
                        ))}
                      </div>
                      <div>
                        <label
                          htmlFor="base-upload"
                          className="block cursor-pointer rounded-[28px] border border-white/10 bg-[#2F2727] px-6 py-4 text-center text-sm font-semibold text-text-primary transition hover:border-brand/60 hover:text-brand"
                        >
                          <span className="flex items-center justify-center gap-2">
                            <Image src="/assets/icons/upload.svg" alt="" width={18} height={18} aria-hidden />
                            {t("ui.canvas.upload")}
                          </span>
                        </label>
                        <input id="base-upload" type="file" accept="image/png,image/jpeg" onChange={handleUpload} className="sr-only" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </section>
  );
}
