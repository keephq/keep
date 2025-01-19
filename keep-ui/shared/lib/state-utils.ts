import { useSWRConfig } from "swr";
import { useCallback } from "react";
export const useRevalidateMultiple = () => {
  const { mutate } = useSWRConfig();
  return useCallback(
    (keys: string[], options: { isExact: boolean } = { isExact: false }) =>
      mutate(
        (key) =>
          typeof key === "string" &&
          keys.some((k) => (options.isExact ? k === key : key.startsWith(k)))
      ),
    [mutate]
  );
};
