import { useI18n } from "@/i18n/hooks/useI18n";
import { createServerApiClient } from "@/shared/api/server";
import AlertsPage from "./ui/alerts";
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

// Metadata is defined statically for SEO purposes
// The i18n translations are applied in the UI components
export const metadata = {
  title: "Keep - Alerts",
  description: "Single pane of glass for all your alerts.",
};
