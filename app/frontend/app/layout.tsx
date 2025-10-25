import "./globals.css";

import type { Metadata } from "next";
import { LocalizationProvider } from "../providers/localization-provider";

export const metadata: Metadata = {
  title: "KIBERone Generation",
  description: "KIBERone SDXL-Turbo Image Generator",
  icons: {
    icon: "/assets/favicon.png",
    shortcut: "/assets/favicon.png",
    apple: "/assets/favicon.png"
  }
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>
        <LocalizationProvider>{children}</LocalizationProvider>
      </body>
    </html>
  );
}
