import IncidentView from "./incident";

type PageProps = {
  params: { id: string };
  searchParams: { [key: string]: string | string[] | undefined };
};

export const metadata = {
  title: "Keep - Incident",
  description: "Incident view",
};

export default function Page(props: PageProps) {
  return <IncidentView incidentId={props.params.id} />;
}
