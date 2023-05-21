import GitHubPage from './github/page';
import ProvidersPage from './providers/page';
import { Suspense } from 'react';
import { getServerSession } from "next-auth/next"


export default async function IndexPage() {
  // https://github.com/nextauthjs/next-auth/pull/5792
  console.log("Loading the main page");
  const id_token = await getServerSession({
    callbacks: { session: ({ token }) => token },
  })

  if(!id_token){
    return <div>Not authorized</div>
  }
  let isGitHubPluginInstalled=false;
  try{
    const url = process.env.GITHUB_PLUGIN_INSTALLED_URL;
    isGitHubPluginInstalled = await fetch(url!, {
      headers: {
        'Authorization': `Bearer ${id_token?.id_token}`
      }
    }).then(res => res.json()).then(data => data.onboarded);
  }
  catch(err){
    console.log("Error fetching GitHub plugin installed status:", err);
    if (err instanceof Error) {
        return <div>Error: {err.message}</div>
    }
    return <div>502 backend error</div>
  }
  console.log("Main page loaded");


  return (
    <div>
      <Suspense fallback={<div>Loading...</div>}>
      {/* @ts-expect-error Async Server Component */}
        {isGitHubPluginInstalled ? <ProvidersPage/>: <GitHubPage />}
      </Suspense>
    </div>
  )
};
