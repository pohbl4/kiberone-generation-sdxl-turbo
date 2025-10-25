import dynamic from "next/dynamic";

import Header from "../../../components/header";
import HeroSection from "../../../components/hero-section";
import PromptPanel from "../../../components/prompt-panel";
import ResultPanel from "../../../components/result-panel";
import AuthWatcher from "../../../components/auth-watcher";

const CanvasPanel = dynamic(() => import("../../../components/canvas-panel"), {
  ssr: false
});

export default function AppPage() {
  return (
    <div className="min-h-screen overflow-x-hidden bg-background text-text-primary">
      <div className="flex justify-center">
        <div className="flex w-full max-w-[1280px] origin-top scale-[0.8] transform flex-col px-6 pt-10 pb-0 sm:px-10">
          <Header />
          <AuthWatcher />
          <main className="mt-12 flex flex-col gap-10">
            <HeroSection />
            <section className="rounded-[40px] bg-surface">
              <div className="flex flex-col gap-10 p-8">
                <PromptPanel />
                <div className="flex flex-col gap-10 lg:grid lg:grid-cols-2 lg:items-start lg:gap-10">
                  <CanvasPanel />
                  <ResultPanel />
                </div>
              </div>
            </section>
          </main>
        </div>
      </div>
    </div>
  );
}
