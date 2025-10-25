declare module "use-image" {
  import type { DependencyList } from "react";

  type UseImageReturn = [HTMLImageElement | undefined, "loaded" | "loading" | "failed"];

  export default function useImage(
    url: string,
    crossOrigin?: string,
    imageAttrs?: Record<string, unknown>
  ): UseImageReturn;

  export function useImage(
    url: string,
    crossOrigin?: string,
    imageAttrs?: Record<string, unknown>,
    deps?: DependencyList
  ): UseImageReturn;
}
