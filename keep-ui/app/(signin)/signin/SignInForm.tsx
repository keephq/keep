"use client";

import { signIn, getProviders } from "next-auth/react";
import { Text, TextInput, Button, Card } from "@tremor/react";
import Image from "next/image";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import "../../globals.css";
import { authenticate, revalidateAfterAuth } from "@/app/actions/authactions";
import { useRouter } from "next/navigation";

export interface Provider {
  id: string;
  name: string;
  type: string;
  signinUrl: string;
  callbackUrl: string;
}

export interface Providers {
  auth0?: Provider;
  credentials?: Provider;
  keycloak?: Provider;
  "microsoft-entra-id"?: Provider;
}

interface SignInFormInputs {
  username: string;
  password: string;
}

export default function SignInForm({ params }: { params?: { amt: string } }) {
  console.log("Init SignInForm");
  const [providers, setProviders] = useState<Providers | null>(null);
  const [isRedirecting, setIsRedirecting] = useState(false);
  const router = useRouter();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<SignInFormInputs>();

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
          signIn(
            "auth0",
            { callbackUrl: "/" },
            { acr_values: `amt:${params.amt}` }
          );
        } else {
          signIn("auth0", { callbackUrl: "/" });
        }
      } else if (providers.keycloak) {
        console.log("Signing in with keycloak provider");
        signIn("keycloak", { callbackUrl: "/" });
      } else if (providers["microsoft-entra-id"]) {
        console.log("Signing in with Azure AD provider");
        signIn("microsoft-entra-id", { callbackUrl: "/" });
      } else if (
        providers.credentials &&
        providers.credentials.name == "NoAuth"
      ) {
        signIn("credentials", { callbackUrl: "/" });
      }
    }
  }, [providers, params]);

  const onSubmit = async (data: SignInFormInputs) => {
    try {
      const result = await authenticate(data.username, data.password);

      if (!result.success) {
        setError("root", {
          message: result.error,
        });
        return <></>;
      }

      // Set redirecting state before navigation
      setIsRedirecting(true);

      // Add a small delay before redirect to ensure state update
      await new Promise((resolve) => setTimeout(resolve, 100));
      router.replace("/incidents");

      // Disable form interactions during redirect
      await revalidateAfterAuth();
      return <></>;
    } catch (error) {
      setError("root", {
        message: "An unexpected error occurred",
      });
      setIsRedirecting(false);
    }
  };

  // Show loading state during redirect
  if (isRedirecting) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-tremor-background-subtle p-4">
        <Card
          className="w-full max-w-md p-8"
          decoration="top"
          decorationColor="orange"
        >
          <div className="flex flex-col items-center gap-6">
            <div className="relative w-32 h-32">
              <Image
                src="/keep_big.svg"
                alt="Keep Logo"
                width={128}
                height={128}
                priority
                className="object-contain"
              />
            </div>
            <Text className="text-tremor-title font-bold text-tremor-content-strong">
              Authentication successful, redirecting...
            </Text>
          </div>
        </Card>
      </div>
    );
  }

  if (providers?.credentials) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-tremor-background-subtle p-4">
        <Card
          className="w-full max-w-md p-8"
          decoration="top"
          decorationColor="orange"
        >
          <div className="flex flex-col items-center gap-6">
            <div className="relative w-32 h-32">
              <Image
                src="/keep_big.svg"
                alt="Keep Logo"
                width={128}
                height={128}
                priority
                className="object-contain"
              />
            </div>

            <Text className="text-tremor-title font-bold text-tremor-content-strong">
              Sign in to Keep
            </Text>

            <form
              className="w-full space-y-6"
              onSubmit={handleSubmit(onSubmit)}
            >
              <div className="space-y-2">
                <Text className="text-tremor-default font-medium text-tremor-content-strong">
                  Username
                </Text>
                <TextInput
                  {...register("username", {
                    required: "Username is required",
                  })}
                  type="text"
                  placeholder="Enter your username"
                  className="w-full"
                  error={!!errors.username}
                  disabled={isSubmitting || isRedirecting}
                />
                {errors.username && (
                  <Text className="text-sm text-red-500 mt-1">
                    {errors.username.message}
                  </Text>
                )}
              </div>

              <div className="space-y-2">
                <Text className="text-tremor-default font-medium text-tremor-content-strong">
                  Password
                </Text>
                <TextInput
                  {...register("password", {
                    required: "Password is required",
                  })}
                  type="password"
                  placeholder="Enter your password"
                  className="w-full"
                  error={!!errors.password}
                  disabled={isSubmitting || isRedirecting}
                />
                {errors.password && (
                  <Text className="text-sm text-red-500 mt-1">
                    {errors.password.message}
                  </Text>
                )}
              </div>

              <Button
                type="submit"
                size="lg"
                className="w-full bg-tremor-brand hover:bg-tremor-brand-emphasis text-tremor-brand-inverted"
                disabled={isSubmitting || isRedirecting}
                loading={isSubmitting || isRedirecting}
              >
                {isSubmitting
                  ? "Signing in..."
                  : isRedirecting
                  ? "Redirecting..."
                  : "Sign in"}
              </Button>

              {errors.root && (
                <div className="w-full rounded-md bg-red-50 p-4">
                  <Text className="text-sm text-red-500 text-center">
                    {errors.root.message}
                  </Text>
                </div>
              )}
            </form>
          </div>
        </Card>
      </div>
    );
  }

  return <>Redirecting to authentication...</>;
}
