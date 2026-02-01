import { redirect } from "next/navigation";

// This is just a redirect from legacy route
export async function GET(
  request: Request,
  props: { params: Promise<{ id: string }> }
) {
  redirect(`/incidents/${(await props.params).id}/alerts`);
}
