import { signIn } from "@/auth";

import { providerMap } from "@/auth";
import { redirect } from "next/navigation";
import { NextRequest, NextResponse } from "next/server";

export const GET = async (req: NextRequest) => {
  const searchParams = req.nextUrl.searchParams;
  const redirectTo = searchParams.get("callbackUrl") ?? "/";

  if (providerMap.has("auth0")) {
    console.log("Signing in with auth0 provider");
    // if (params?.amt) {
    //   signIn("auth0", { redirectTo }, { acr_values: `amt:${params.amt}` });
    // } else {
    await signIn("auth0", { redirectTo });
    // }
  } else if (providerMap.has("keycloak")) {
    console.log("Signing in with keycloak provider");
    await signIn("keycloak", { redirectTo });
  } else if (providerMap.has("microsoft-entra-id")) {
    console.log("Signing in with Azure AD provider");
    await signIn("microsoft-entra-id", { redirectTo });
  } else if (
    providerMap.has("credentials") &&
    providerMap.get("credentials") === "NoAuth"
  ) {
    console.log("Signing in with NoAuth");
    await signIn("credentials", { redirectTo });
  }

  redirect("/signin/form");
};
