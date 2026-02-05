// proxyFetch.node.ts
import { ProxyAgent, fetch as undici } from "undici";
import type { ProxyFetchFn } from "./proxyFetch";

export const createProxyFetch = async (): Promise<ProxyFetchFn | undefined> => {
  const proxyUrl =
    process.env.HTTP_PROXY ||
    process.env.HTTPS_PROXY ||
    process.env.http_proxy ||
    process.env.https_proxy;

  if (!proxyUrl) {
    return undefined;
  }

  const dispatcher = new ProxyAgent(proxyUrl);

  return function proxy(
    ...args: Parameters<typeof fetch>
  ): ReturnType<typeof fetch> {
    // @ts-expect-error `undici` has a `duplex` option
    return undici(args[0], { ...args[1], dispatcher });
  };
};
