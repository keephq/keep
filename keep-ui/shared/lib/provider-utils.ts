import { Provider } from "@/app/(keep)/providers/providers";

interface ProvidersData {
  providers: { [key: string]: { providers: Provider[] } };
}

/**
 * Determines whether a provider is considered installed.
 *
 * @param provider - The provider to check for installation status
 * @param providers - A collection of providers, either as a key-value mapping or an array
 * @returns A boolean indicating if the provider is installed
 *
 * @remarks
 * A provider is considered installed if:
 * - Its `installed` property is true, or
 * - There are no other providers of the same type with a non-empty configuration
 */
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
