import React from "react";
import { Text } from "@tremor/react";
import "../../globals.css";

export type ErrorType =
  | "Configuration"
  | "AccessDenied"
  | "Verification"
  | "Default";

interface AuthErrorProps {
  error: ErrorType | string | null;
  status?: string | null;
  authType?: string;
  authEnvVars?: Record<string, string>;
}

export const AuthError = ({
  error,
  status,
  authType,
  authEnvVars,
}: AuthErrorProps) => {
  const errorMessages: Record<ErrorType, string> = {
    Configuration:
      "There was a problem with the authentication setup. It is probably due to a configuration error on the authentication server.\n\nPlease contact the administrator.",
    AccessDenied: "You don't have permission to access this resource.",
    Verification:
      "The verification link has expired or is invalid. Please request a new one.",
    Default: "An unexpected error occurred. Please try again.",
  };

  const getErrorMessage = (errorType: string | null): string => {
    if (!errorType) return errorMessages.Default;
    return errorMessages[errorType as ErrorType] || errorMessages.Default;
  };

  return (
    <div className="w-full">
      <Text className="text-xl font-bold mb-4 text-center">
        {error === "Configuration"
          ? "Server Configuration Error"
          : "Authentication Error"}
      </Text>

      <div className="w-full">
        <div className="w-full rounded-md bg-red-50 p-6">
          <Text className="text-base text-red-500 text-center whitespace-pre-line mb-8">
            {getErrorMessage(error)}
          </Text>
          <div className="font-mono bg-red-100 p-2 rounded break-all">
            {authType && (
              <Text className="text-base text-red-500">
                AUTH_TYPE: {authType}
              </Text>
            )}
            {authEnvVars &&
              Object.entries(authEnvVars).map(([key, value]) => (
                <Text key={key} className="text-base text-red-500 mt-2">
                  {key}: {value}
                </Text>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthError;
