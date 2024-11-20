import { auth } from "@/auth";
import { getApiURL } from "@/utils/apiUrl";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";

export default async function InstallFromOAuth({
  params,
  searchParams,
}: {
  params: { providerType: string };
  searchParams: { [key: string]: string };
}) {
  const accessToken = await auth();
  // this is server so we can use the old getApiURL
  const apiUrl = getApiURL();
  const cookieStore = cookies();
  const verifier = cookieStore.get("verifier");
  const installWebhook = cookieStore.get("oauth2_install_webhook");
  const pullingEnabled = cookieStore.get("oauth2_pulling_enabled");

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
        install_webhook: installWebhook ? installWebhook.value : false,
        pulling_enabled: pullingEnabled ? pullingEnabled.value : false,
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
