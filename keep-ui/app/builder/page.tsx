import PageClient from "./page.client";
import { Suspense } from "react";
import Loading from "../loading";

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <PageClient />
    </Suspense>
  );
}

export const metadata = {
  title: "Keep - Builder",
  description: "Build alerts with a visual workflow designer.",
};
