"use client";
import { useSession } from "next-auth/react";

export function useHydratedSession() {
  // NextAuthProvider hydrates the context with the server session.
  return useSession();
}
