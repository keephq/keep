import { useI18n } from "@/i18n/hooks/useI18n";
import DashboardPage from "./dashboard";

export default function Page() {
  return <DashboardPage />;
}

export const metadata = {
  title: "Keep - Dashboards",
  description: "Single pane of glass for all your alerts.",
};
