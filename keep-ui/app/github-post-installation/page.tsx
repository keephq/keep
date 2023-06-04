import { getServerSession } from "../../utils/customAuth";
import { redirect } from "next/navigation";
import { getApiURL } from "../../utils/apiUrl";
export default async function GithubPostInstallationPage({
  searchParams,
}: {
  searchParams: { installation_id: string; setup_action: string };
}) {
  // https://github.com/nextauthjs/next-auth/pull/5792
  const accessToken = (
    await getServerSession({
      callbacks: { session: ({ token }) => token },
    })
  )?.accessToken;

  let installedSuccessfully = false;
  try {
    const apiUrl = getApiURL();
    installedSuccessfully = await fetch(`${apiUrl}/tenant/github`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${accessToken}`,
      },
      body: JSON.stringify(searchParams),
    })
      .then((res) => {
        if (!res.ok) {
          throw new Error(`HTTP error ${res.status}`);
        }
        return res.json();
      })
      .then((data) => data.success);

    // Handle successful installation
    if (installedSuccessfully) {
      console.log("Installation successful, redirecting");
    } else {
      // TODO handle unsuccessful installation
      console.log("Installation unsuccessful, redirecting");
    }
  } catch (err) {
    console.log("Error installing the GitHub app", err);
    if (err instanceof Error) {
      return <div>Error: {err.message}</div>;
    }
    return <div>502 backend error</div>;
  }
  redirect("/");
}
