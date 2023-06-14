import GitHubPage from "../github/page";
import { getServerSession } from "../../utils/customAuth";
import ErrorComponent from "../error";
import PostHogClient from "../posthog-server";
import { getApiURL } from "../../utils/apiUrl";
import { authOptions } from "../../pages/api/auth/[...nextauth]";


export default async function CicdPage() {
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
    <GitHubPage isInstalled={isGitHubPluginInstalled}/>
  )
}
