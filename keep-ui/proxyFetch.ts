// proxyFetch.ts
let proxyFetch: typeof fetch | undefined;

export async function initProxyFetch() {
  const proxyUrl =
    process.env.HTTP_PROXY ||
    process.env.HTTPS_PROXY ||
    process.env.http_proxy ||
    process.env.https_proxy;

  if (proxyUrl && typeof window === "undefined") {
    const { ProxyAgent, fetch: undici } = await import("undici");
    const dispatcher = new ProxyAgent(proxyUrl);
    return (...args: Parameters<typeof fetch>): ReturnType<typeof fetch> => {
      // @ts-expect-error `undici` has a `duplex` option
      return undici(args[0], { ...args[1], dispatcher });
    };
  }
  return undefined;
}
