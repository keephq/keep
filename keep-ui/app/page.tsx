import GitHubPage from "./github/page";
import ProvidersPage from "./providers/page";
import { Suspense } from "react";
import { getServerSession } from "../utils/customAuth";
import ErrorComponent from "./error";

export default async function IndexPage() {
  // https://github.com/nextauthjs/next-auth/pull/5792
  const accessToken = (
    await getServerSession({
      callbacks: { session: ({ token }) => token },
    })
  )?.accessToken as string;

  let isGitHubPluginInstalled = false;
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL!;
    isGitHubPluginInstalled = await fetch(`${apiUrl}/tenant/onboarded`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
    })
      .then((res) => res.json())
      .then((data) => data.onboarded);
  } catch (err) {
    // Inside the catch block
    console.log("Error fetching GitHub plugin installed status:", err);
    const apiUrl = process.env.NEXT_PUBLIC_API_URL!;
    const url = `${apiUrl}/tenant/onboarded`;

    if (err instanceof Error) {
      return (
        <ErrorComponent errorMessage={`Error: ${err.message}`} url={url} />
      );
    }
    return <ErrorComponent errorMessage="502 backend error" url={url} />;
  }

  return (
    <div>
      <Suspense fallback={<div>Loading...</div>}>
        {/* @ts-expect-error Async Server Component */}
        {isGitHubPluginInstalled ? <ProvidersPage /> : <GitHubPage />}
      </Suspense>
    </div>
  );
}
