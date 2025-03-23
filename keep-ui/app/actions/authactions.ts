"use server";

import { signIn } from "@/auth";
import { AuthenticationError, AuthErrorCodes } from "@/errors";
import { revalidatePath } from "next/cache";

export async function authenticate(username: string, password: string) {
  try {
    const result = await signIn("credentials", {
      username,
      password,
      redirect: false,
    });

    // Check if result exists before returning success
    if (result) {
      return { success: true, data: result };
    } else {
      // Handle the case where signIn returns undefined
      console.log(
        "Authentication failed: No response from authentication service"
      );
      return {
        success: false,
        error: "Authentication failed: No response from authentication service",
      };
    }
  } catch (error) {
    if (error instanceof AuthenticationError) {
      switch (error.code) {
        case AuthErrorCodes.INVALID_CREDENTIALS:
          return {
            success: false,
            error: "Invalid username or password",
          };
        case AuthErrorCodes.CONNECTION_REFUSED:
          return {
            success: false,
            error: "The authentication service is currently unavailable",
          };
        case AuthErrorCodes.SERVICE_UNAVAILABLE:
          return {
            success: false,
            error: "Authentication service is currently unavailable",
          };
        case AuthErrorCodes.INVALID_TOKEN:
          return {
            success: false,
            error: "Failed to generate authentication token",
          };
        default:
          return {
            success: false,
            error: "An unexpected authentication error",
          };
      }
    }

    throw new Error("Authentication failed");
  }
}

export async function revalidateAfterAuth() {
  "use server";
  // Revalidate all paths that might include the navbar
  revalidatePath("/", "layout");
}
