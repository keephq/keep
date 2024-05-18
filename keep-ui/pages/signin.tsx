import { signIn, getProviders } from "next-auth/react";
import { useEffect, useState } from "react";
import { authOptions } from "pages/api/auth/[...nextauth]";

import {__NEXTAUTH} from "next-auth/client/_utils";

interface Providers {
  auth0?: {
    // Define the properties that your auth0 provider has
    name: string;
    type: string;
    signinUrl: string;
  };
  credentials?: {
    // Similarly define for credentials provider
    name: string;
    type: string;
    signinUrl: string;
  };
  keycloak?: {
    // Similarly define for keycloak provider
    name: string;
    type: string;
    signinUrl: string;
  };
}


export async function getServerSideProps(context: any) {
  return {
    props: { params: context.query }, // will be passed to the page component as props
  };
}

export default function SignIn({ params }: { params?: { amt: string } }) {
  const [providers, setProviders] = useState<Providers | null>(null);
  const providersNew = authOptions.providers;

  useEffect(() => {
    async function fetchProviders() {
      // const response = await getProviders();
      setProviders(authOptions.providers as Providers);
    }

    fetchProviders();
  }, []);

  useEffect(() => {
    if (providersNew) {
      if (providersNew[0].id == "auth0") {
        console.log("Signing in with auth0 provider");
        if (params?.amt) {
          // Do we have a token from AWS Marketplace? redirect to auth0 with the token
          signIn(
            "auth0",
            { callbackUrl: "/" },
            { acr_values: `amt:${params.amt}` }
          );
        } else {
          signIn("auth0", { callbackUrl: "/" });
        }
      } else if (providersNew[0].id  == "credentials") {
        console.log("Signing in with credentials provider");
        debugger;
        signIn("credentials", { callbackUrl: "/" });
      } else if (providers.keycloak) {
        console.log('Signing in with keycloak provider');
        signIn('keycloak', { callbackUrl: "/" });
      }
    }
  }, [providers]);

  return <div>Redirecting for authentication...</div>;
}
