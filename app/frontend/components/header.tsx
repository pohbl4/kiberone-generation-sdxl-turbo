"use client";

import Image from "next/image";
import { useTranslation } from "../providers/localization-provider";

export default function Header() {
  const { language, setLanguage, t } = useTranslation();

  return (
    <header className="flex flex-col gap-8">
      <div className="flex flex-col gap-8 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:gap-10">
          <div className="w-full max-w-[187px]">
            <Image
              src="/assets/logo.svg"
              alt={t("ui.header.logo_alt")}
              width={187}
              height={71}
              priority
              className="h-auto w-full"
            />
          </div>
          <div className="space-y-1 text-white w-full lg:max-w-[520px]">
            <p className="text-lg font-bold leading-snug text-text-primary sm:text-xl md:text-2xl">
              {t("ui.header.tagline_primary")}
            </p>
            <p className="text-lg font-semibold leading-snug text-text-primary sm:text-xl md:text-2xl">
              {t("ui.header.tagline_secondary")}
            </p>
          </div>
        </div>
        <div className="flex justify-end">
          <div className="flex gap-1 rounded-full bg-[#2F2727] p-1 text-sm font-semibold">
            <LanguagePill
              active={language === "en"}
              label={t("ui.header.lang_en")}
              onClick={() => setLanguage("en")}
            />
            <LanguagePill
              active={language === "ru"}
              label={t("ui.header.lang_ru")}
              onClick={() => setLanguage("ru")}
            />
          </div>
        </div>
      </div>
    </header>
  );
}

type LanguagePillProps = {
  active: boolean;
  label: string;
  onClick: () => void;
};

function LanguagePill({ active, label, onClick }: LanguagePillProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full px-5 py-2 transition ${
        active
          ? "bg-brand text-brand-contrast shadow-[0_18px_40px_rgba(244,183,64,0.35)]"
          : "text-text-muted hover:text-text-primary"
      }`}
    >
      {label}
    </button>
  );
}
