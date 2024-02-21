import { signIn, getProviders } from 'next-auth/react';
import { useEffect, useState } from 'react';

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


export default function SignIn() {
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
        console.log('Signing in with auth0 provider');
        signIn('auth0', { callbackUrl: "/" });
      } else if (providers.credentials) {
        console.log('Signing in with credentials provider');
        signIn('credentials', { callbackUrl: "/" });
      } else if (providers.keycloak) {
        console.log('Signing in with keycloak provider');
        signIn('keycloak', { callbackUrl: "/" });
      }
    }
  }, [providers]);

  return <div>Redirecting for authentication...</div>;
}
