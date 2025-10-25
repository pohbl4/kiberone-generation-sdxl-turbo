"use client";

import Image from "next/image";
import { useMemo } from "react";
import { useTranslation } from "../providers/localization-provider";

type HeroTitleParts = {
  intro: string;
  brand: string;
  bridge: string;
  emphasis: string;
};

type CardConfig = {
  id: string;
  text: string;
  highlight: string;
  imageSrc: string;
};

export default function HeroSection() {
  const { t, language } = useTranslation();

  const titleParts: HeroTitleParts = useMemo(() => {
    if (language === "ru") {
      return { intro: "Быть в", brand: "KIBERone", bridge: "— это", emphasis: "БЫТЬ КРУТЫМ!" };
    }
    return { intro: "Being at", brand: "KIBERone", bridge: "means", emphasis: "BEING AWESOME!" };
  }, [language]);

  const cards: CardConfig[] = useMemo(
    () => [
      {
        id: "create",
        text: t("ui.hero.cards.0.title"),
        highlight: t("ui.hero.cards.0.highlight"),
        imageSrc: "/assets/image1.png"
      },
      {
        id: "think",
        text: t("ui.hero.cards.1.title"),
        highlight: t("ui.hero.cards.1.highlight"),
        imageSrc: "/assets/image2.png"
      },
      {
        id: "future",
        text: t("ui.hero.cards.2.title"),
        highlight: t("ui.hero.cards.2.highlight"),
        imageSrc: "/assets/image3.png"
      }
    ],
    [t]
  );

  return (
    <section className="rounded-[40px] border border-white/10 bg-surface px-8 py-10 shadow-panel">
      <div className="flex flex-col gap-10">
        <div className="space-y-4">
          <h2 className="text-left text-[32px] font-semibold leading-[1.2] text-white sm:text-[36px] md:text-[40px]">
            <span className="text-white/80">{titleParts.intro} </span>
            <span className="text-brand">{titleParts.brand}</span>
            <span className="text-white/80"> {titleParts.bridge} </span>
            <span className="text-brand">{titleParts.emphasis}</span>
          </h2>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {cards.map((card) => (
            <HeroCard
              key={card.id}
              text={card.text}
              highlight={card.highlight}
              imageSrc={card.imageSrc}
            />
          ))}
        </div>
      </div>
    </section>
  );
}

type HeroCardProps = {
  text: string;
  highlight: string;
  imageSrc: string;
};

function HeroCard({ text, highlight, imageSrc }: HeroCardProps) {
  const [before, after] = useMemo(() => {
    if (!highlight || !text.includes(highlight)) {
      return [text, ""];
    }
    const [prefix, suffix] = text.split(highlight);
    return [prefix, suffix];
  }, [highlight, text]);

  return (
    <article className="flex flex-col items-center gap-5 rounded-[32px] border border-white/10 bg-[#2F2727] p-6 text-center">
      <div className="w-full overflow-hidden rounded-3xl border border-white/10 bg-[#3A302E]">
        <Image
          src={imageSrc}
          alt={text}
          width={640}
          height={361}
          className="h-full w-full object-cover"
        />
      </div>
      <p className="text-lg font-medium leading-snug text-white">
        {before}
        {highlight ? <span className="text-brand">{highlight}</span> : null}
        {after}
      </p>
    </article>
  );
}
