import { Provider } from "@/app/(keep)/providers/providers";

export function isProviderInstalled(
  provider: Pick<Provider, "type" | "installed">,
  providers: Provider[]
) {
  return (
    provider.installed ||
    !Object.values(providers || {}).some(
      (p) =>
        p.type === provider.type && p.config && Object.keys(p.config).length > 0
    )
  );
}
