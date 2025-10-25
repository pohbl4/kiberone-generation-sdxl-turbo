"use client";

import { useMemo } from "react";
import { useTranslation } from "../providers/localization-provider";
import { useAppStore } from "../store/app-store";

const PANEL_CONTAINER_CLASS = "rounded-[40px] border border-white/10 bg-surface px-8 py-8 shadow-panel";

const PROMPT_EXAMPLES = ["ui.prompt.examples.0", "ui.prompt.examples.1"] as const;

export default function PromptPanel() {
  const { t } = useTranslation();
  const prompt = useAppStore((state) => state.prompt);
  const setPrompt = useAppStore((state) => state.setPrompt);

  const examples = useMemo(() => PROMPT_EXAMPLES.map((key) => t(key)), [t]);

  return (
    <section className={PANEL_CONTAINER_CLASS}>
      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h2 className="text-2xl font-semibold text-white">{t("ui.prompt.label")}</h2>
          <span className="rounded-full bg-[#2F2727] px-4 py-1 text-xs font-semibold uppercase tracking-[0.32em] text-text-muted">
            {prompt.length}/500
          </span>
        </div>
        <div className="flex flex-wrap gap-3">
          {examples.map((example) => (
            <button
              key={example}
              type="button"
              className="rounded-full border border-white/10 bg-[#2F2727] px-5 py-2 text-sm font-medium text-text-primary transition hover:border-brand/60 hover:text-brand"
              onClick={() => setPrompt(example)}
            >
              {example}
            </button>
          ))}
        </div>
        <textarea
          id="prompt-input"
          rows={1}
          value={prompt}
          onChange={(event) => setPrompt(event.target.value.slice(0, 500))}
          maxLength={500}
          placeholder={t("ui.prompt.placeholder")}
          aria-label={t("ui.prompt.placeholder")}
          className="h-14 w-full resize-none rounded-[28px] border border-white/10 bg-[#2F2727] px-6 py-3 text-base text-text-primary placeholder:text-text-muted focus:border-brand focus:outline-none focus:ring-0"
        />
      </div>
    </section>
  );
}
