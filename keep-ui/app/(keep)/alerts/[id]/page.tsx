import { createServerApiClient } from "@/shared/api/server";
import AlertsPage from "../alerts";
import { getInitalFacets } from "@/features/filter/api";

type PageProps = {
  params: { id: string };
  searchParams: { [key: string]: string | string[] | undefined };
};

export default async function Page({ params }: PageProps) {
  const api = await createServerApiClient();
  const initialFacets = await getInitalFacets(api, "alerts");
  return <AlertsPage presetName={params.id} initalFacets={initialFacets} />;
}

export const metadata = {
  title: "Keep - Alerts",
  description: "Single pane of glass for all your alerts.",
};
