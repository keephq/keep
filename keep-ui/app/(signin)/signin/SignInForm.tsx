"use client";

import { signIn, getProviders } from "next-auth/react";
import { Text, TextInput, Button } from "@tremor/react";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { authenticate, revalidateAfterAuth } from "@/app/actions/authactions";
import { useRouter } from "next/navigation";
import "../../globals.css";

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

export default function SignInForm({
  params,
  searchParams,
}: {
  params?: { amt: string };
  searchParams: { [key: string]: string | string[] | undefined };
}) {
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
        const callbackUrl = (searchParams["callbackUrl"] as string) || "/";
        const tenantId = searchParams["tenantId"];

        // If tenantId is present in query params, add it to the callback URL
        const callbackWithTenant = tenantId
          ? `${callbackUrl}${
              callbackUrl.includes("?") ? "&" : "?"
            }tenantId=${tenantId}`
          : callbackUrl;

        signIn("credentials", {
          callbackUrl: callbackWithTenant,
        });
      }
    }
  }, [providers, params, searchParams]);

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
      <Text className="text-tremor-title h-full flex items-center justify-center font-bold text-tremor-content-strong">
        Authentication successful, redirecting...
      </Text>
    );
  }

  if (providers?.credentials) {
    return (
      <>
        <Text className="text-tremor-title font-bold text-tremor-content-strong">
          Log in to your account
        </Text>

        <form className="w-full space-y-6" onSubmit={handleSubmit(onSubmit)}>
          {errors.root && (
            <div className="w-full rounded-md bg-red-50 p-4">
              <Text className="text-sm text-red-500 text-center">
                {errors.root.message}
              </Text>
            </div>
          )}
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
            color="orange"
            variant="primary"
            className="w-full"
            disabled={isSubmitting || isRedirecting}
            loading={isSubmitting || isRedirecting}
          >
            {isSubmitting
              ? "Signing in..."
              : isRedirecting
              ? "Redirecting..."
              : "Sign in"}
          </Button>
        </form>
      </>
    );
  }

  return (
    <Text className="h-full flex items-center justify-center text-tremor-title font-bold text-tremor-content-strong">
      Redirecting to authentication...
    </Text>
  );
}
