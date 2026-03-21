import { useI18n } from "@/i18n/hooks/useI18n";
import Mapping from "./mapping";

export default function Page() {
  return <Mapping />;
}

export const metadata = {
  title: "Keep - Event Mapping",
  description: "Add dynamic context to your alerts with mapping",
};
