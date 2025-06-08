import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
const celQueryParamName = "cel";
const defaultOptions = { enableQueryParams: false, defaultCel: "" };

export function useCelState({
  enableQueryParams,
  defaultCel,
}: typeof defaultOptions) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const searchParamsRef = useRef(searchParams);
  searchParamsRef.current = searchParams;
  const [celState, setCelState] = useState(() => {
    if (!enableQueryParams) {
      return defaultCel || "";
    }

    return searchParams.get(celQueryParamName) || defaultCel || "";
  });

  // Track if this is the initial mount
  const isInitialMount = useRef(true);
  const previousPathname = useRef(pathname);

  // Clean up cel param when pathname changes (but not on initial mount)
  useEffect(() => {
    // Skip cleanup on initial mount
    if (isInitialMount.current) {
      isInitialMount.current = false;
      previousPathname.current = pathname;
      return;
    }

    // Only run cleanup if pathname actually changed
    if (previousPathname.current === pathname) {
      return;
    }

    previousPathname.current = pathname;

    return () => {
      const newParams = new URLSearchParams(searchParamsRef.current);
      if (newParams.has(celQueryParamName)) {
        newParams.delete(celQueryParamName);
        router.replace(
          `${window.location.pathname}${newParams.toString() ? "?" + newParams.toString() : ""}`
        );
      }
    };
  }, [pathname, router]);

  useEffect(() => {
    if (!enableQueryParams) return;
    const paramsCopy = new URLSearchParams(searchParamsRef.current);

    if (paramsCopy.get(celQueryParamName) === celState) {
      return;
    }

    paramsCopy.delete(celQueryParamName);

    if (celState && celState !== defaultCel) {
      paramsCopy.set(celQueryParamName, celState);
    }

    router.replace(
      `${window.location.pathname}${paramsCopy.toString() ? "?" + paramsCopy.toString() : ""}`
    );
  }, [celState, enableQueryParams, defaultCel, router]);

  return [celState, setCelState] as const;
}
