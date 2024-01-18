import { getServerSession } from "next-auth/next";
import { authOptions } from "pages/api/auth/[...nextauth]";
import { getApiURL } from "utils/apiUrl";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";

export default async function InstallFromOAuth({
  params,
  searchParams,
}: {
  params: { providerType: string };
  searchParams: { [key: string]: string };
}) {
  const accessToken = await getServerSession(authOptions);
  const apiUrl = getApiURL();
  const cookieStore = cookies();
  const verifier = cookieStore.get("verifier");

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
        verifier: verifier ? verifier.value : null,
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
