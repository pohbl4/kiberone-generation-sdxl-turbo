"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import i18next from "i18next";
import { I18nextProvider, initReactI18next, useTranslation as useI18NextTranslation } from "react-i18next";

const COOKIE_MAX_AGE_DAYS = 365;
const COOKIE_SAME_SITE = "Lax";

const getCookie = (name: string): string | undefined => {
  if (typeof document === "undefined") {
    return undefined;
  }

  const prefix = `${name}=`;
  const cookie = document.cookie.split("; ").find((entry) => entry.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : undefined;
};

const setCookie = (name: string, value: string, maxAgeDays: number, sameSite: string) => {
  if (typeof document === "undefined") {
    return;
  }

  const expires = new Date(Date.now() + maxAgeDays * 24 * 60 * 60 * 1000).toUTCString();
  const encodedValue = encodeURIComponent(value);
  document.cookie = `${name}=${encodedValue}; expires=${expires}; path=/; SameSite=${sameSite}`;
};

type Language = "ru" | "en";

type TranslationKey =
  | "ui.login.title"
  | "ui.login.username"
  | "ui.login.username_hint"
  | "ui.login.password"
  | "ui.login.submit"
  | "ui.header.logout"
  | "ui.header.logo_alt"
  | "ui.header.lang_ru"
  | "ui.header.lang_en"
  | "ui.header.tagline_primary"
  | "ui.header.tagline_secondary"
  | "ui.hero.cards.0.title"
  | "ui.hero.cards.0.highlight"
  | "ui.hero.cards.1.title"
  | "ui.hero.cards.1.highlight"
  | "ui.hero.cards.2.title"
  | "ui.hero.cards.2.highlight"
  | "ui.prompt.label"
  | "ui.prompt.placeholder"
  | "ui.prompt.examples.0"
  | "ui.prompt.examples.1"
  | "ui.canvas.title"
  | "ui.canvas.upload"
  | "ui.canvas.brush"
  | "ui.canvas.eraser"
  | "ui.canvas.thickness"
  | "ui.canvas.color"
  | "ui.canvas.undo"
  | "ui.canvas.redo"
  | "ui.canvas.clear"
  | "ui.canvas.templates.mountains"
  | "ui.canvas.templates.city"
  | "ui.canvas.templates.lab"
  | "ui.canvas.templates.forest"
  | "ui.result.title"
  | "ui.result.status.queued"
  | "ui.result.status.running"
  | "ui.result.status.done"
  | "ui.result.status.error"
  | "ui.result.status.degraded"
  | "ui.result.actions.again"
  | "ui.result.actions.improve"
  | "ui.result.actions.apply"
  | "ui.result.actions.undo"
  | "ui.result.actions.download"
  | "ui.errors.base_required"
  | "ui.errors.invalid_credentials"
  | "ui.errors.api_unreachable"
  | "ui.errors.generic"
  | "ui.errors.network";

type Dictionary = Record<TranslationKey, string>;

type Resources = Record<Language, { translation: Dictionary }>;

const resources: Resources = {
  ru: {
    translation: {
      "ui.login.title": "Вход",
      "ui.login.username": "Логин",
      "ui.login.password": "Пароль",
      "ui.login.submit": "Войти",
      "ui.login.username_hint": "KIBERoneStudent",
      "ui.header.logout": "Выход",
      "ui.header.logo_alt": "Логотип KIBERone",
      "ui.header.lang_ru": "Рус",
      "ui.header.lang_en": "Eng",
      "ui.header.tagline_primary": "Кибершкола будущего",
      "ui.header.tagline_secondary": "Которая помогает детям войти в 1% успешных людей мира",
      "ui.hero.cards.0.title": "Создавать IT проекты",
      "ui.hero.cards.0.highlight": "IT проекты",
      "ui.hero.cards.1.title": "Мыслить шире",
      "ui.hero.cards.1.highlight": "шире",
      "ui.hero.cards.2.title": "Опережать будущее",
      "ui.hero.cards.2.highlight": "будущее",
      "ui.prompt.label": "Промпт",
      "ui.prompt.placeholder": "Введите промпт",
      "ui.prompt.examples.0": "Городской пейзаж, студия Ghibli, иллюстрация",
      "ui.prompt.examples.1": "Средиземноморский город, импрессионистская живопись, фиолетовый оттенок",
      "ui.canvas.title": "Холст",
      "ui.canvas.upload": "Загрузить изображение (JPG, PNG)",
      "ui.canvas.brush": "Кисть",
      "ui.canvas.eraser": "Ластик",
      "ui.canvas.thickness": "Толщина",
      "ui.canvas.color": "Цвет",
      "ui.canvas.undo": "Назад (эскиз)",
      "ui.canvas.redo": "Вперёд (эскиз)",
      "ui.canvas.clear": "Очистить эскиз",
      "ui.canvas.templates.mountains": "Горы и природа",
      "ui.canvas.templates.city": "Городская сцена",
      "ui.canvas.templates.lab": "Научная лаборатория",
      "ui.canvas.templates.forest": "Лесная тропа",
      "ui.result.title": "Результат",
      "ui.result.status.queued": "В очереди",
      "ui.result.status.running": "Генерация…",
      "ui.result.status.done": "Готово",
      "ui.result.status.error": "Ошибка",
      "ui.result.status.degraded": "Снижено качество из-за нагрузки",
      "ui.result.actions.again": "Ещё",
      "ui.result.actions.improve": "Улучшить",
      "ui.result.actions.apply": "Перенести на холст",
      "ui.result.actions.undo": "Назад",
      "ui.result.actions.download": "Скачать",
      "ui.errors.base_required": "Сначала выберите базовое изображение",
      "ui.errors.invalid_credentials": "Неверный пароль",
      "ui.errors.api_unreachable": "API недоступно. Убедитесь, что запущен сервер FastAPI.",
      "ui.errors.generic": "Не удалось выполнить запрос",
      "ui.errors.network": "Сеть недоступна. Проверьте подключение или настройки API."
    }
  },
  en: {
    translation: {
      "ui.login.title": "Sign in",
      "ui.login.username": "Username",
      "ui.login.password": "Password",
      "ui.login.submit": "Sign in",
      "ui.login.username_hint": "KIBERoneStudent",
      "ui.header.logout": "Log out",
      "ui.header.logo_alt": "KIBERone logo",
      "ui.header.lang_ru": "Rus",
      "ui.header.lang_en": "Eng",
      "ui.header.tagline_primary": "CYBERschool of the Future",
      "ui.header.tagline_secondary": "Where kids become global leaders",
      "ui.hero.cards.0.title": "Creating IT projects",
      "ui.hero.cards.0.highlight": "IT projects",
      "ui.hero.cards.1.title": "Thinking bigger",
      "ui.hero.cards.1.highlight": "bigger",
      "ui.hero.cards.2.title": "Staying ahead of the future",
      "ui.hero.cards.2.highlight": "future",
      "ui.prompt.label": "Prompt",
      "ui.prompt.placeholder": "Enter prompt here",
      "ui.prompt.examples.0": "Cityscape, Studio Ghibli, illustration",
      "ui.prompt.examples.1": "Mediterranean town, impressionist painting, violet hue",
      "ui.canvas.title": "Canvas",
      "ui.canvas.upload": "Upload image (JPG, PNG)",
      "ui.canvas.brush": "Brush",
      "ui.canvas.eraser": "Eraser",
      "ui.canvas.thickness": "Thickness",
      "ui.canvas.color": "Colour",
      "ui.canvas.undo": "Undo sketch",
      "ui.canvas.redo": "Redo sketch",
      "ui.canvas.clear": "Clear",
      "ui.canvas.templates.mountains": "Mountains & nature",
      "ui.canvas.templates.city": "City scene",
      "ui.canvas.templates.lab": "Science lab",
      "ui.canvas.templates.forest": "Forest trail",
      "ui.result.title": "Result",
      "ui.result.status.queued": "Queued",
      "ui.result.status.running": "Generating…",
      "ui.result.status.done": "Done",
      "ui.result.status.error": "Error",
      "ui.result.status.degraded": "Quality reduced due to load",
      "ui.result.actions.again": "Next",
      "ui.result.actions.improve": "Enchance",
      "ui.result.actions.apply": "Move to Canvas",
      "ui.result.actions.undo": "Back",
      "ui.result.actions.download": "Download",
      "ui.errors.base_required": "Select a base image first",
      "ui.errors.invalid_credentials": "Incorrect password",
      "ui.errors.api_unreachable": "API is unreachable. Make sure the FastAPI server is running.",
      "ui.errors.generic": "The request could not be completed",
      "ui.errors.network": "Network error. Check your connection or API settings."
    }
  }
};

const COOKIE_NAME = "lang";

interface LocalizationContextValue {
  language: Language;
  setLanguage: (lang: Language) => void;
}

const LocalizationContext = createContext<LocalizationContextValue | undefined>(undefined);

let initialized = false;

function ensureI18n(initialLanguage: Language) {
  if (!initialized) {
    i18next.use(initReactI18next).init({
      resources,
      fallbackLng: initialLanguage,
      lng: initialLanguage,
      interpolation: { escapeValue: false },
      keySeparator: false,
      returnNull: false
    });
    initialized = true;
  }
}

export function LocalizationProvider({ children }: { children: ReactNode }) {
  ensureI18n("ru");
  const [language, setLanguageState] = useState<Language>("ru");

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const paramsLang = new URLSearchParams(window.location.search).get("lang");
    const cookieLang = getCookie(COOKIE_NAME);
    const nextLang =
      paramsLang === "ru" || paramsLang === "en"
        ? (paramsLang as Language)
        : cookieLang === "ru" || cookieLang === "en"
        ? (cookieLang as Language)
        : language;
    if (nextLang !== language) {
      setLanguageState(nextLang);
    }
  }, []);

  useEffect(() => {
    ensureI18n(language);
    i18next.changeLanguage(language);
    setCookie(COOKIE_NAME, language, COOKIE_MAX_AGE_DAYS, COOKIE_SAME_SITE);
    if (typeof document !== "undefined") {
      document.documentElement.lang = language;
    }
  }, [language]);

  const setLanguage = useCallback((lang: Language) => {
    setLanguageState(lang);
  }, []);

  const contextValue = useMemo(
    () => ({
      language,
      setLanguage
    }),
    [language, setLanguage]
  );

  return (
    <I18nextProvider i18n={i18next}>
      <LocalizationContext.Provider value={contextValue}>{children}</LocalizationContext.Provider>
    </I18nextProvider>
  );
}

export function useTranslation() {
  const context = useContext(LocalizationContext);
  if (!context) {
    throw new Error("useTranslation must be used within LocalizationProvider");
  }
  const { t: translate } = useI18NextTranslation();
  return {
    language: context.language,
    setLanguage: context.setLanguage,
    t: (key: TranslationKey, options?: Record<string, unknown>) => translate(key, options) as string
  };
}

export type { TranslationKey };
