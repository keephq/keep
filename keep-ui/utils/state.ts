import { useSWRConfig } from "swr";

type MutateArgs = [string, (data: any) => any];

export const mutateLocalMultiple = (args: MutateArgs[]) => {
  const { cache } = useSWRConfig();
  args.forEach(([key, mutateFunction]) => {
    const currentData = cache.get(key as string);
    cache.set(key as string, mutateFunction(currentData));
  });
};

export const useRevalidateMultiple = () => {
  const { mutate } = useSWRConfig();
  return (keys: string[]) =>
    mutate((key) => typeof key === "string" && keys.includes(key));
};
