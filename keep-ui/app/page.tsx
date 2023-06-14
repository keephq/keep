
import ProvidersPage from "./providers/page";
import { Suspense } from "react";
import Loading from "./loading";
import Frill from "./frill";

export const metadata = {
  title: "Keep Console",
  description: "Alerting and on-call management for modern engineering teams.",
};

export default async function IndexPage() {
  console.log("Loading Index Page")

  return (
    <>
      <Frill />
      <div>
        <Suspense fallback={<Loading/>}>
          <ProvidersPage />
        </Suspense>
      </div>
    </>
  );
}
