import { Provider } from "@/app/(keep)/providers/providers";

interface ProvidersData {
  providers: { [key: string]: { providers: Provider[] } };
}

export function isProviderInstalled(
  provider: Provider,
  providers: ProvidersData | Provider[]
) {
  return (
    provider.installed ||
    !Object.values(providers || {}).some(
      (p) =>
        p.type === provider.type && p.config && Object.keys(p.config).length > 0
    )
  );
}
