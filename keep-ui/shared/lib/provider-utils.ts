import { Provider } from "@/shared/api/providers";

/**
 * Determines whether a provider is properly installed and available for use.
 * 
 * A provider is considered installed if:
 * 1. It has the 'installed' flag set to true, OR
 * 2. There are NO other providers of the same type with a non-empty config
 * 
 * @param provider The provider to check
 * @param providers Array of all available providers
 * @returns boolean indicating if the provider is installed
 */
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
