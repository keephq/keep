import PageClient from "./page.client";
import { Suspense } from "react";
import Loading from "../loading";

export default function Page({ workflow }: { workflow: string }) {
  return (
    <Suspense fallback={<Loading />}>
      <PageClient workflow={workflow} />
    </Suspense>
  );
}

export const metadata = {
  title: "Keep - Builder",
  description: "Build alerts with a visual workflow designer.",
};
