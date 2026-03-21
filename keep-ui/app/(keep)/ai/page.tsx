import { useI18n } from "@/i18n/hooks/useI18n";
import { AIPlugins } from "./ai-plugins";

export default function Page() {
  return <AIPlugins />;
}

export const metadata = {
  title: "Keep - AI Correlation",
  description:
    "Correlate Alerts and Incidents with AI to identify patterns and trends.",
};
