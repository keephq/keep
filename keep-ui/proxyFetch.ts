// proxyFetch.ts

// We only export the type from this file
export type ProxyFetchFn = (
  ...args: Parameters<typeof fetch>
) => ReturnType<typeof fetch>;

// This function will be imported dynamically only in Node.js environment
export const createProxyFetch = async (): Promise<ProxyFetchFn | undefined> => {
  return undefined;
};
