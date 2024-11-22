import DashboardPage from "./dashboard";

type PageProps = {
  params: { id: string };
  searchParams: { [key: string]: string | string[] | undefined };
};

export default function Page({ params }: PageProps) {
  return <DashboardPage />;
}

export const metadata = {
  title: "Keep - Dashboards",
  description: "Single pane of glass for all your alerts.",
};
