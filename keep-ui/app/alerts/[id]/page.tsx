import AlertsPage from "../alerts";
import { fetchAllAlertsForPreset } from "@/app/alerts/api";
import { getServerSession } from "next-auth/next";
import { authOptions } from "@/pages/api/auth/[...nextauth]";

type PageProps = {
  params: { id: string };
  searchParams: { [key: string]: string | string[] | undefined };
};

export default async function Page({ params }: PageProps) {
  const session = await getServerSession(authOptions);
  const alerts = await fetchAllAlertsForPreset(session, params.id);
  return <AlertsPage presetName={params.id} initialAlerts={alerts} />;
}

export const metadata = {
  title: "Keep - Alerts",
  description: "Single pane of glass for all your alerts.",
};
