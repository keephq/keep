import NextAuth from "next-auth";
import { customFetch } from "next-auth";
import { config, authType, proxyUrl } from "@/auth.config";
import { ProxyAgent, fetch as undici } from "undici";
import MicrosoftEntraID from "next-auth/providers/microsoft-entra-id";
import { AuthType } from "@/utils/authenticationType";
import Credentials from "next-auth/providers/credentials";
import { User } from "next-auth";

// Implement the tenant switch provider directly in auth.ts
const tenantSwitchProvider = Credentials({
  id: "tenant-switch",
  name: "Tenant Switch",
  credentials: {
    tenantId: { label: "Tenant ID", type: "text" },
    sessionAsJson: { label: "Session", type: "text" },
  },
  async authorize(credentials, req): Promise<User | null> {
    if (!credentials?.tenantId) {
      throw new Error("No tenant ID provided");
    }

    let session = JSON.parse(credentials.sessionAsJson as string);

    // Fallback to getting the user from cookies if session is not available
    let user: any;
    if (session?.user) {
      user = session.user;
    } else {
      // Try to get us  er info from JWT token
      const token = (req as any)?.token;
      if (token) {
        user = {
          id: token.sub,
          name: token.name,
          email: token.email,
          tenantId: token.tenantId,
          tenantIds: token.tenantIds,
        };
      }
    }

    if (!user || !user.tenantIds) {
      console.error("Cannot switch tenant: User information not available");
      throw new Error("User not authenticated or missing tenant information");
    }

    // Verify the tenant ID is valid for this user
    const validTenant = user.tenantIds.find(
      (t: { tenant_id: string }) => t.tenant_id === credentials.tenantId
    );

    if (!validTenant) {
      console.error(`Invalid tenant ID: ${credentials.tenantId}`);
      throw new Error("Invalid tenant ID for this user");
    }

    console.log(`Switching to tenant: ${credentials.tenantId}`);

    let accessToken = JSON.parse(user.accessToken) as any;
    accessToken["tenant_id"] = credentials.tenantId;
    user.accessToken = JSON.stringify(accessToken);
    // Return the user with the new tenant ID
    return {
      ...user,
      tenantId: credentials.tenantId,
    };
  },
});

// Add the tenant switch provider to the config
// Use type assertion to add the tenant switch provider to the config
// This bypasses TypeScript's type checking for this specific operation
config.providers = [...config.providers, tenantSwitchProvider] as any;

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

// Modify the session callback to ensure tenantIds are available
const originalSessionCallback = config.callbacks.session;
config.callbacks.session = async (params) => {
  const session = await originalSessionCallback(params);

  // Make sure tenantIds from the token are added to the session
  if (params.token && "tenantIds" in params.token) {
    session.user.tenantIds = params.token.tenantIds as {
      tenant_id: string;
      tenant_name: string;
    }[];
  }

  // Also copy tenantIds from user object if available
  if (params.user && "tenantIds" in params.user) {
    session.user.tenantIds = params.user.tenantIds;
  }

  return session;
};

// Modify the JWT callback to preserve tenantIds
const originalJwtCallback = config.callbacks.jwt;
config.callbacks.jwt = async (params) => {
  const token = await originalJwtCallback(params);

  // Make sure tenantIds from the user are preserved in the token
  if (params.user && "tenantIds" in params.user) {
    token.tenantIds = params.user.tenantIds;
  }

  return token;
};

console.log("Starting Keep frontend with auth type:", authType);
export const { handlers, auth, signIn, signOut } = NextAuth(config);
