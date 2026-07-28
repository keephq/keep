"use client";
import { useSession } from "next-auth/react";

export function useHydratedSession() {
  return useSession();
}
