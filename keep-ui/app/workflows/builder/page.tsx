import PageClient from "./page.client";
import { Suspense } from "react";
import Loading from "../../loading";

type PageProps = {
  params: { workflow: string; workflowId: string };
  searchParams: { [key: string]: string | string[] | undefined };
};

export default function Page({ params, searchParams }: PageProps) {
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
