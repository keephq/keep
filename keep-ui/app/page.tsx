import GitHubPage from './github/page';
import ProvidersPage from './providers/page';
import { Suspense } from 'react';
import { getServerSession } from "next-auth/next"
import ErrorComponent from './error';

export default async function IndexPage() {
  // https://github.com/nextauthjs/next-auth/pull/5792
  console.log("Loading the main page");
  const accessToken = (
    await getServerSession({
      callbacks: { session: ({ token }) => token },
    })
  )?.accessToken as string;

  if (!accessToken) {
    return <div>Not authorized</div>;
  }

  let isGitHubPluginInstalled = false;
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL!;
    isGitHubPluginInstalled = await fetch(`${apiUrl}/tenant/onboarded`, {
      headers: {
        'Authorization': `Bearer ${accessToken}`
      }
    }).then(res => res.json()).then(data => data.onboarded);
  }
  // Inside the catch block
  catch (err) {
      console.log("Error fetching GitHub plugin installed status:", err);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL!;
      const url = `${apiUrl}/tenant/onboarded`;

      if (err instanceof Error) {
        return <ErrorComponent errorMessage={`Error: ${err.message}`} url={url} />;
      }
      return <ErrorComponent errorMessage="502 backend error" url={url} />;
    }

  console.log("Main page loaded");

  return (
    <div>
      <Suspense fallback={<div>Loading...</div>}>
        {/* @ts-expect-error Async Server Component */}
        {isGitHubPluginInstalled ? <ProvidersPage /> : <GitHubPage />}
      </Suspense>
    </div>
  );
}
