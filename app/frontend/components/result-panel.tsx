"use client";

import Image from "next/image";
import { useMemo } from "react";
import { useTranslation } from "../providers/localization-provider";
import { useAppStore } from "../store/app-store";
import { useGenerationController } from "../hooks/use-generation-controller";
import { API_BASE_RAW } from "../lib/api-config";

const PANEL_CONTAINER_CLASS = "rounded-[40px] border border-white/10 bg-surface px-8 py-8 shadow-panel";

const TEMPLATE_PREVIEWS: Record<string, string> = {
  "template-mountains": "/assets/pattern1.png",
  "template-city": "/assets/pattern2.png",
  "template-lab": "/assets/pattern3.png",
  "template-forest": "/assets/pattern4.png"
};

const DEFAULT_TEMPLATE_PREVIEW = TEMPLATE_PREVIEWS["template-mountains"];

export default function ResultPanel() {
  const { t } = useTranslation();
  const baseImage = useAppStore((state) => state.baseImage);
  const results = useAppStore((state) => state.results);
  const {
    currentResult,
    regenerate,
    improve,
    undo,
    applyResultToCanvas,
    downloadCurrent,
    isGenerating
  } = useGenerationController();

  const apiOrigin = useMemo(() => {
    try {
      return new URL(API_BASE_RAW).origin;
    } catch {
      return "";
    }
  }, []);

  const fallbackImageUrl = useMemo(() => {
    if (!baseImage) {
      return DEFAULT_TEMPLATE_PREVIEW;
    }

    if (baseImage.placeholderSlot) {
      const preview = TEMPLATE_PREVIEWS[baseImage.placeholderSlot];
      if (preview) {
        return preview;
      }
    }

    if (!baseImage.url) {
      return DEFAULT_TEMPLATE_PREVIEW;
    }

    if (baseImage.url.startsWith("http")) {
      return baseImage.url;
    }

    if (apiOrigin) {
      return `${apiOrigin}${baseImage.url}`;
    }

    return baseImage.url;
  }, [apiOrigin, baseImage]);

  const displayImageUrl = currentResult?.url ?? fallbackImageUrl;

  return (
    <section className={PANEL_CONTAINER_CLASS}>
      <div className="flex flex-col gap-6">
        <h2 className="text-2xl font-semibold text-white">{t("ui.result.title")}</h2>

        <div className="flex flex-col gap-6 rounded-[36px] bg-[#2F2727] p-6">
          <div className="flex flex-col items-center gap-4">
            <Image
              src={displayImageUrl}
              alt="Result"
              width={512}
              height={512}
              unoptimized
              className="aspect-square w-full max-w-[448px] rounded-2xl object-cover"
            />
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <ResultActionButton
              icon="/assets/icons/back.svg"
              label={t("ui.result.actions.undo")}
              onClick={undo}
              disabled={isGenerating || results.length <= 1}
            />
            <ResultActionButton
              icon="/assets/icons/next.svg"
              label={t("ui.result.actions.again")}
              onClick={regenerate}
              disabled={isGenerating || !results.length}
            />
            <ResultActionButton
              icon="/assets/icons/enchance.svg"
              label={t("ui.result.actions.improve")}
              onClick={improve}
              disabled={isGenerating || !currentResult?.seed}
              variant="primary"
            />
            <ResultActionButton
              icon="/assets/icons/move.svg"
              label={t("ui.result.actions.apply")}
              onClick={applyResultToCanvas}
              disabled={isGenerating || !currentResult}
            />
            <ResultActionButton
              icon="/assets/icons/download.svg"
              label={t("ui.result.actions.download")}
              onClick={downloadCurrent}
              disabled={!currentResult?.downloadToken}
            />
          </div>
        </div>
      </div>
    </section>
  );
}

type ResultActionButtonProps = {
  label: string;
  icon?: string;
  onClick: () => void;
  disabled?: boolean;
  variant?: "primary" | "ghost";
};

function ResultActionButton({ label, icon, onClick, disabled, variant = "ghost" }: ResultActionButtonProps) {
  const baseClasses =
    "flex flex-1 min-w-[120px] items-center justify-center gap-2 rounded-full border px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60";
  const variantClasses =
    variant === "primary"
      ? "border-brand bg-brand text-brand-contrast shadow-[0_18px_40px_rgba(244,183,64,0.35)]"
      : "border-white/10 bg-[#2F2727] text-text-primary hover:border-brand/60 hover:text-brand";

  return (
    <button type="button" onClick={onClick} disabled={disabled} className={`${baseClasses} ${variantClasses}`}>
      {icon ? <Image src={icon} alt="" width={18} height={18} aria-hidden /> : null}
      {label}
    </button>
  );
}
