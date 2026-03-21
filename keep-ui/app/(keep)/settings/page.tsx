import { useI18n } from "@/i18n/hooks/useI18n";
import { Suspense } from "react";
import SettingsPage from "./settings.client";

export default function Page() {
  return (
    <Suspense>
      <SettingsPage />
    </Suspense>
  );
}

export const metadata = {
  title: "Keep - Settings",
  description: "Configure your Keep.",
};
