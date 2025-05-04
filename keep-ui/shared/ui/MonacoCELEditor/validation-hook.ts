import { useApi } from "@/shared/lib/hooks/useApi";
import { editor } from "monaco-editor";
import { useEffect, useMemo, useState } from "react";
import useSWR from "swr";

interface CelExpressionValidationMarker {
  columnStart: number;
  columnEnd: number;
}

export function useCelValidation(cel: string): editor.IMarkerData[] {
  const api = useApi();
  const uri = `/cel/validate`;
  const [celToValidate, setCelToValidate] = useState<string>(cel);

  // debounce the cel input to avoid too many requests
  useEffect(() => {
    const timeout = setTimeout(() => {
      setCelToValidate(cel);
    }, 500);
    return () => {
      clearTimeout(timeout);
    };
  }, [cel, setCelToValidate]);

  const { data, error, isLoading } = useSWR<CelExpressionValidationMarker[]>(
    () => (api.isReady() ? uri + celToValidate : null),
    () => {
      if (!celToValidate) {
        return [];
      }

      return api.post(uri, { cel });
    }
  );

  const validationErrors: editor.IMarkerData[] = useMemo(() => {
    if (!data) {
      return [];
    }

    return data.map((marker) => ({
      severity: 8, // 8 is error
      startLineNumber: 1,
      endLineNumber: 1,
      startColumn: Math.max(marker.columnStart - 1, 0),
      endColumn: Math.min(marker.columnEnd + 1, celToValidate.length),
      message: "The error is found at this position",
      source: "CEL",
    }));
  }, [data, celToValidate]);

  return isLoading ? [] : validationErrors;
}
