import PageClient from "./page.client";
import { Suspense } from "react";
import Loading from "../loading";

export default function Page({
  workflow,
  workflowId,
}: {
  workflow: string;
  workflowId: string;
}) {
  return (
    <Suspense fallback={<Loading />}>
      <PageClient workflow={workflow} workflowId={workflowId} />
    </Suspense>
  );
}

export const metadata = {
  title: "Keep - Builder",
  description: "Build alerts with a visual workflow designer.",
};
