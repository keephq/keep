import { useSWRConfig } from "swr";

export const useRevalidateMultiple = () => {
  const { mutate } = useSWRConfig();
  return (keys: string[]) =>
    mutate((key) => typeof key === "string" && keys.includes(key));
};
