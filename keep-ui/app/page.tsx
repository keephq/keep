import GitHubPage from "./github/page";
import ProvidersPage from "./providers/page";
import { Suspense } from "react";
import { getServerSession } from "../utils/customAuth";
import ErrorComponent from "./error";
import PostHogClient from "./posthog-server";
import { getApiURL } from "../utils/apiUrl";
import Frill from "./frill";
import { authOptions } from "../pages/api/auth/[...nextauth]";

export const metadata = {
  title: "Keep Console",
  description: "Alerting and on-call management for modern engineering teams.",
};

export default async function IndexPage() {
  const accessToken = await getServerSession(authOptions);

  let isGitHubPluginInstalled = false;
  try {
    const apiUrl = getApiURL();
    isGitHubPluginInstalled = await fetch(`${apiUrl}/tenant/onboarded`, {
      headers: {
        Authorization: `Bearer ${accessToken?.accessToken}`,
      },
      cache: "no-store",
    })
      .then((res) => res.json())
      .then((data) => data.onboarded);
  } catch (err) {
    // Inside the catch block
    console.log("Error fetching GitHub plugin installed status:", err);
    const apiUrl = getApiURL();
    const url = `${apiUrl}/tenant/onboarded`;
    // capture the event
    PostHogClient().safeCapture("User started without keep api", accessToken);
    if (err instanceof Error) {
      return (
        <ErrorComponent errorMessage={`Error: ${err.message}`} url={url} />
      );
    }
    return <ErrorComponent errorMessage="502 backend error" url={url} />;
  }

  return (
    <>
      <Frill />
      <div>
        <Suspense fallback={<div>Loading...</div>}>
          {/* @ts-expect-error Async Server Component */}
          {isGitHubPluginInstalled ? <ProvidersPage /> : <GitHubPage />}
        </Suspense>
      </div>
    </>
  );
}
