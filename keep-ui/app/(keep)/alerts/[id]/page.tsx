import { createServerApiClient } from "@/shared/api/server";
import AlertsPage from "../alerts";
import { getInitialFacets } from "@/features/filter/api";

type PageProps = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export default async function Page(props: PageProps) {
  const params = await props.params;
  const api = await createServerApiClient();
  const initialFacets = await getInitialFacets(api, "alerts");
  return <AlertsPage presetName={params.id} initialFacets={initialFacets} />;
}

export const metadata = {
  title: "Keep - Alerts",
  description: "Single pane of glass for all your alerts.",
};
