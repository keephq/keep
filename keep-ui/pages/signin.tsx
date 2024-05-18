import { signIn, getProviders } from "next-auth/react";
import { useEffect, useState } from "react";
import { authOptions } from "pages/api/auth/[...nextauth]";
import {useConfig} from "utils/hooks/useConfig";

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

  const providersNew = authOptions.providers;

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
        signIn("credentials", { callbackUrl: "/" });
      }
    }
  }, []);

  return <div>Redirecting for authentication...</div>;
}
