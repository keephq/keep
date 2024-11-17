import PageClient from "./page.client";
import { Suspense } from "react";
import Loading from "../../loading";

type PageProps = {
  params: Promise<{ workflow: string; workflowId: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export default async function Page(props: PageProps) {
  const params = await props.params;
  return (
    <Suspense fallback={<Loading />}>
      <PageClient workflow={params.workflow} workflowId={params.workflowId} />
    </Suspense>
  );
}

export const metadata = {
  title: "Keep - Builder",
  description: "Build alerts with a visual workflow designer.",
};
