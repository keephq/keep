"use client";

import { Text, TextInput, Button, Card } from "@tremor/react";
import Image from "next/image";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { authenticate, revalidateAfterAuth } from "@/app/actions/authactions";
import { useRouter } from "next/navigation";
import { SignInLoader } from "./ui/loader";
import { SignInFormPageProps } from "./page";

interface SignInFormInputs {
  username: string;
  password: string;
}

export function CredentialsSignInForm({ searchParams }: SignInFormPageProps) {
  console.log("Init SignInForm");
  const redirectTo = searchParams?.callbackUrl ?? "/";

  const [isRedirecting, setIsRedirecting] = useState(false);
  const router = useRouter();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    setError,
  } = useForm<SignInFormInputs>();

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
      // TODO: Redirect to the correct page redirectTo
      router.replace(redirectTo);

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
    return <SignInLoader text="Authentication successful, redirecting..." />;
  }

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

          <form className="w-full space-y-6" onSubmit={handleSubmit(onSubmit)}>
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
