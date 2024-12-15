import { useSWRConfig } from "swr";

export const useRevalidateMultiple = () => {
  const { mutate } = useSWRConfig();
  return (keys: string[], options: { isExact: boolean } = { isExact: false }) =>
    mutate(
      (key) =>
        typeof key === "string" &&
        keys.some((k) => (options.isExact ? k === key : key.startsWith(k)))
    );
};
