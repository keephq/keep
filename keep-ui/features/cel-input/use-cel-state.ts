import { useDebouncedValue } from "@/utils/hooks/useDebouncedValue";
import { useEffect, useState } from "react";

const celQueryParamName = "cel";
const defaultOptions = { enableQueryParams: false, defaultCel: "" };

function updateQueryString(queryString: string) {
  var newurl =
    window.location.origin + window.location.pathname + queryString
      ? `?${queryString}`
      : "";
  console.log("Ihor", newurl);

  window.history.pushState({ path: newurl }, "", newurl);
}

export function useCelState(options: {
  enableQueryParams: boolean;
  defaultCel: string;
}) {
  options = options ?? defaultOptions;

  const [celState, setCelState] = useState<string>(
    new URLSearchParams(window.location.search).get(celQueryParamName) ||
      options.defaultCel ||
      ""
  );
  const [debouncedCel] = useDebouncedValue(celState, 500);

  useEffect(() => {
    return () => {
      const currentQueryParams = new URLSearchParams(window.location.search);
      currentQueryParams
        .entries()
        .filter(([key, value]) => key === celQueryParamName)
        .forEach(([key, value]) => currentQueryParams.delete(key, value));
      updateQueryString(currentQueryParams.toString());
    };
  }, []);

  useEffect(() => {
    if (!options.enableQueryParams) {
      return;
    }

    const currentQueryParams = new URLSearchParams(window.location.search);

    currentQueryParams
      .entries()
      .filter(([key, value]) => key === celQueryParamName)
      .forEach(([key, value]) => currentQueryParams.delete(key, value));

    if (debouncedCel !== null && debouncedCel !== options.defaultCel) {
      currentQueryParams.append(celQueryParamName, debouncedCel);
    }

    updateQueryString(currentQueryParams.toString());
  }, [options.enableQueryParams, options.defaultCel, debouncedCel]);

  return [celState, setCelState] as [typeof celState, typeof setCelState];
}
