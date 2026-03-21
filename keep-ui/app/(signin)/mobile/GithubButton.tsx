"use client";
import { useI18n } from "@/i18n/hooks/useI18n";
// GithubButton.tsx - Client Component

import { Button } from "@tremor/react";
import { Github } from "lucide-react";

export function GithubButton() {
  const { t } = useI18n();
  return (
    <Button
      icon={Github}
      size="lg"
      className="mt-4"
      onClick={() => window.open("https://github.com/keephq/keep", "_blank")}
    >
      {t("auth.login.githubButton")}
    </Button>
  );
}
