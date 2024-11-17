import AlertsPage from "../alerts.client";

type PageProps = {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export default async function Page(props: PageProps) {
  const params = await props.params;
  return <AlertsPage presetName={params.id} />;
}

export const metadata = {
  title: "Keep - Alerts",
  description: "Single pane of glass for all your alerts.",
};
