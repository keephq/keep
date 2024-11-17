import { signIn, getProviders } from "next-auth/react";
import { useEffect, useState } from "react";

interface Provider {
  id: string;
  name: string;
  type: string;
  signinUrl: string;
  callbackUrl: string;
}

interface Providers {
  auth0?: Provider;
  credentials?: Provider;
  keycloak?: Provider;
  "azure-ad"?: Provider;
}

export async function getServerSideProps(context: any) {
  return {
    props: { params: context.query }, // will be passed to the page component as props
  };
}

export default function SignIn({
  params,
}: {
  params?: { amt: string; callbackUrl: string };
}) {
  const [providers, setProviders] = useState<Providers | null>(null);
  const callbackUrl = params?.callbackUrl || "/";

  useEffect(() => {
    async function fetchProviders() {
      const response = await getProviders();
      setProviders(response as Providers);
    }

    fetchProviders();
  }, []);

  useEffect(() => {
    if (providers) {
      if (providers.auth0) {
        console.log("Signing in with auth0 provider");
        if (params?.amt) {
          // Do we have a token from AWS Marketplace? redirect to auth0 with the token
          signIn("auth0", { callbackUrl }, { acr_values: `amt:${params.amt}` });
        } else {
          signIn("auth0", { callbackUrl });
        }
      } else if (providers.credentials) {
        console.log("Signing in with credentials provider");
        signIn("credentials", { callbackUrl });
      } else if (providers.keycloak) {
        console.log("Signing in with keycloak provider");
        signIn("keycloak", { callbackUrl });
      } else if (providers["azure-ad"]) {
        console.log("Signing in with Azure AD provider");
        signIn("azure-ad", { callbackUrl });
      } else {
        console.log("No provider found");
        console.log(providers);
      }
    }
  }, [providers, params, callbackUrl]);

  return <div>Redirecting for authentication...</div>;
}
