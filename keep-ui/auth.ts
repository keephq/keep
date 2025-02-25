import NextAuth from "next-auth";
import { customFetch } from "next-auth";
import { config, authType, proxyUrl } from "@/auth.config";
import { ProxyAgent, fetch as undici } from "undici";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import { AuthType } from "@/utils/authenticationType";

function proxyFetch(
  ...args: Parameters<typeof fetch>
): ReturnType<typeof fetch> {
  const isDebug = config.debug;
  console.log(
    "Proxy called for URL:",
    args[0] instanceof Request ? args[0].url : args[0]
  );

  const dispatcher = new ProxyAgent(proxyUrl!);

  if (args[0] instanceof Request) {
    const request = args[0];
    // @ts-expect-error `undici` has a `duplex` option
    return undici(request.url, {
      ...args[1],
      method: request.method,
      headers: request.headers as HeadersInit,
      body: request.body,
      dispatcher,
    }).then(async (response) => {
      if (isDebug) {
        // Clone the response to log it without consuming the body
        const clonedResponse = response.clone();

        console.log("Proxy response status:", clonedResponse.status);
        console.log(
          "Proxy response headers:",
          Object.fromEntries(clonedResponse.headers)
        );

        // Log response body only in debug mode
        try {
          const body = await clonedResponse.text();
          console.log("Proxy response body:", body);
        } catch (err) {
          console.error("Error reading response body:", err);
        }
      }
      return response;
    });
  }

  // @ts-expect-error `undici` has a `duplex` option
  return undici(args[0], { ...(args[1] || {}), dispatcher }).then(
    async (response) => {
      if (isDebug) {
        // Clone the response to log it without consuming the body
        const clonedResponse = response.clone();

        console.log("Proxy response status:", clonedResponse.status);
        console.log(
          "Proxy response headers:",
          Object.fromEntries(clonedResponse.headers)
        );

        // Log response body only in debug mode
        try {
          const body = await clonedResponse.text();
          console.log("Proxy response body:", body);
        } catch (err) {
          console.error("Error reading response body:", err);
        }
      }
      return response;
    }
  );
}

// Modify the config if using Azure AD with proxy
if (authType === AuthType.AZUREAD && proxyUrl) {
  const provider = config.providers[0] as ReturnType<typeof MicrosoftEntraID>;

  if (!proxyUrl) {
    console.log("Proxy is not enabled for Azure AD");
  } else {
    console.log("Proxy is enabled for Azure AD:", proxyUrl);
  }

  // Override the `customFetch` symbol in the provider
  provider[customFetch] = async (...args: Parameters<typeof fetch>) => {
    const url = new URL(args[0] instanceof Request ? args[0].url : args[0]);
    console.log("Custom Fetch Intercepted:", url.toString());

    // Handle `.well-known/openid-configuration` logic
    if (url.pathname.endsWith(".well-known/openid-configuration")) {
      console.log("Intercepting .well-known/openid-configuration");
      const response = await proxyFetch(...args);
      const json = await response.clone().json();
      const tenantRe = /microsoftonline\.com\/(\w+)\/v2\.0/;
      const tenantId = provider.issuer?.match(tenantRe)?.[1] ?? "common";
      if (!tenantId) {
        console.error(
          "Failed to extract tenant ID from issuer:",
          provider.issuer
        );
        throw new Error("Failed to extract tenant ID from issuer");
      }
      if (!json.issuer) {
        console.error("Failed to extract issuer from response:", json);
        throw new Error("Failed to extract issuer from response");
      }
      const issuer = json.issuer.replace("{tenantid}", tenantId);
      console.log("Modified issuer:", issuer);
      return Response.json({ ...json, issuer });
    }

    // Fallback for all other requests
    return proxyFetch(...args);
  };

  // Override profile since it uses fetch without customFetch
  provider.profile = async (profile, tokens) => {
    // @tb: this causes 431 Request Header Fields Too Large
    // const profilePhotoSize = 48;
    // console.log("Fetching profile photo via proxy");

    // const response = await proxyFetch(
    //   `https://graph.microsoft.com/v1.0/me/photos/${profilePhotoSize}x${profilePhotoSize}/$value`,
    //   { headers: { Authorization: `Bearer ${tokens.access_token}` } }
    // );

    // let image: string | null = null;
    // if (response.ok && typeof Buffer !== "undefined") {
    //   try {
    //     const pictureBuffer = await response.arrayBuffer();
    //     const pictureBase64 = Buffer.from(pictureBuffer).toString("base64");
    //     image = `data:image/jpeg;base64,${pictureBase64}`;
    //   } catch (error) {
    //     console.error("Error processing profile photo:", error);
    //   }
    // }
    // https://stackoverflow.com/questions/77686104/how-to-resolve-http-error-431-nextjs-next-auth

    return {
      id: profile.sub,
      name: profile.name,
      email: profile.email,
      image: null,
      accessToken: tokens.access_token ?? "",
    };
  };
}

console.log("Starting Keep frontend with auth type:", authType);

export const { handlers, auth, signIn, signOut } = NextAuth(config);
