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
  const [celState, setCelState] = useState(
    () => searchParams.get(celQueryParamName) || defaultCel || ""
  );

  // Clean up cel param when pathname changes
  useEffect(() => {
    return () => {
      const newParams = new URLSearchParams(searchParamsRef.current);
      if (newParams.has(celQueryParamName)) {
        newParams.delete(celQueryParamName);
        router.replace(
          `${window.location.pathname}${newParams.toString() ? "?" + newParams.toString() : ""}`
        );
      }
    };
  }, [pathname]);

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
  }, [celState, enableQueryParams, defaultCel]);

  return [celState, setCelState] as const;
}
