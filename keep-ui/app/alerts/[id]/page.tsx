import AlertsPage from "../alerts";

type PageProps = {
  params: { id: string };
  searchParams: { [key: string]: string | string[] | undefined };
};

export default function Page({ params }: PageProps) {
  return <AlertsPage presetName={params.id} />;
}

export const metadata = {
  title: "Keep - Alerts",
  description: "Single pane of glass for all your alerts.",
};
