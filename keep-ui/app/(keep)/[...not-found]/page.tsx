"use client";
import { useI18n } from "@/i18n/hooks/useI18n";

import { notFound } from "next/navigation";

// https://github.com/vercel/next.js/discussions/50034
export default function NotFoundDummy() {
  notFound();
}
