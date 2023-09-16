import { getServerSession } from "utils/customAuth";
import { authOptions } from "pages/api/auth/[...nextauth]";
import { getApiURL } from "utils/apiUrl";
import { redirect } from "next/navigation";

export default async function InstallFromOAuth({
  params,
  searchParams,
}: {
  params: { providerType: string };
  searchParams: { [key: string]: string };
}) {
  const accessToken = await getServerSession(authOptions);
  const apiUrl = getApiURL();

  const response = await fetch(
    `${apiUrl}/providers/install/oauth2/${params.providerType}`,
    {
      headers: {
        Authorization: `Bearer ${accessToken?.accessToken}`,
        "Content-Type": "application/json",
      },
      method: "POST",
      body: JSON.stringify({
        ...searchParams,
        redirect_uri: `${process.env.NEXTAUTH_URL}/providers/oauth2/${params.providerType}`,
      }),
      cache: "no-store",
    }
  );
  const responseText = await response.text();
  response.ok
    ? redirect("/providers?oauth=success")
    : redirect(`/providers?oauth=failure&reason=${responseText}`);
  return null;
}
