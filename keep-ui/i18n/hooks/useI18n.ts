"use client";

import { useTranslations } from "next-intl";

/**
 * Custom hook that wraps next-intl's useTranslations
 * for easier use across the application.
 */
export function useI18n() {
  const t = useTranslations();
  return { t };
}
