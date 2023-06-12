
import ProvidersPage from "./providers/page";
import { Suspense } from "react";
import Frill from "./frill";

export const metadata = {
  title: "Keep Console",
  description: "Alerting and on-call management for modern engineering teams.",
};

export default async function IndexPage() {


  return (
    <>
      <Frill />
      <div>
        <Suspense fallback={<div>Loading...</div>}>
          {/* @ts-expect-error Async Server Component */}
          <ProvidersPage />
        </Suspense>
        {/* @ts-expect-error Async Server Component */}
        {isGitHubPluginInstalled ? <ProvidersPage /> : <GitHubPage />}
      </div>
    </>
  );
}
