import { signIn, getProviders } from "next-auth/react";
import { useEffect, useState } from "react";

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
}

export async function getServerSideProps(context: any) {
  return {
    props: { params: context.query }, // will be passed to the page component as props
  };
}

export default function SignIn({ params }: { params?: { amt: string } }) {
  const [providers, setProviders] = useState<Providers | null>(null);

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
          signIn(
            "auth0",
            { callbackUrl: "/" },
            { acr_values: `amt:${params.amt}` }
          );
        } else {
          signIn("auth0", { callbackUrl: "/" });
        }
      } else if (providers.credentials) {
        console.log("Signing in with credentials provider");
        signIn("credentials", { callbackUrl: "/" });
      }
    }
  }, [providers]);

  return <div>Redirecting for authentication...</div>;
}
