import { signIn, providerMap } from "@/auth";
import { CredentialsSignInForm } from "./CredentialsSignInForm";
import { SignInLoader } from "./ui/loader";

export type SignInPageProps = {
  params: {
    amt: string;
  };
  searchParams: {
    callbackUrl?: string;
  };
};

export default async function SignInPage({
  params,
  searchParams,
}: SignInPageProps) {
  const redirectTo = searchParams.callbackUrl ?? "/";
  if (providerMap.get("auth0")) {
    console.log("Signing in with auth0 provider");
    if (params?.amt) {
      signIn("auth0", { redirectTo }, { acr_values: `amt:${params.amt}` });
    } else {
      signIn("auth0", { redirectTo });
    }
  } else if (providerMap.get("keycloak")) {
    console.log("Signing in with keycloak provider");
    signIn("keycloak", { redirectTo });
  } else if (providerMap.get("microsoft-entra-id")) {
    console.log("Signing in with Azure AD provider");
    signIn("microsoft-entra-id", { redirectTo });
  } else if (
    providerMap.get("credentials") &&
    providerMap.get("credentials")?.name == "NoAuth"
  ) {
    signIn("credentials", { redirectTo });
  }
  if (providerMap.get("credentials")) {
    return (
      <CredentialsSignInForm params={params} searchParams={searchParams} />
    );
  }
  return <SignInLoader text="Redirecting to authentication..." />;
}
