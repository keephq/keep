import { useI18n } from "@/i18n/hooks/useI18n";
import APIKeySettings from "./api-key-settings";

export default function APIKeysSubTab() {
  return <APIKeySettings selectedTab="api-key" />;
}
