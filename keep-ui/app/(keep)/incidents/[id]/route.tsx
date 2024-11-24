import { redirect } from "next/navigation";

type PageProps = {
  params: { id: string };
  searchParams: { [key: string]: string | string[] | undefined };
};

// This is just a redirect from legacy route
export function GET(request: Request, props: PageProps) {
  redirect(`/incidents/${props.params.id}/alerts`);
}
