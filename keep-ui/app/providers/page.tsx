import { Suspense } from "react";
import Loading from "../loading";
import ProvidersPage from "./page.client";

export default function Page() {
  return (
    <Suspense fallback={<Loading />}>
      <ProvidersPage />
    </Suspense>
  );
}

export const metadata = {
  title: "Keep - Providers",
  description: "Connect providers to Keep to make your alerts better.",
};
