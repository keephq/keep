import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { getServerApiClient } from "@/shared/lib/api/getServerApiClient";

export default async function InstallFromOAuth({
  params,
  searchParams,
}: {
  params: { providerType: string };
  searchParams: { [key: string]: string };
}) {
  const api = await getServerApiClient();
  const cookieStore = cookies();
  const verifier = cookieStore.get("verifier");
  const installWebhook = cookieStore.get("oauth2_install_webhook");
  const pullingEnabled = cookieStore.get("oauth2_pulling_enabled");

  try {
    const response = await api.post(
      `/providers/install/oauth2/${params.providerType}`,
      {
        ...searchParams,
        redirect_uri: `${process.env.NEXTAUTH_URL}/providers/oauth2/${params.providerType}`,
        verifier: verifier ? verifier.value : null,
        install_webhook: installWebhook ? installWebhook.value : false,
        pulling_enabled: pullingEnabled ? pullingEnabled.value : false,
      },
      {
        cache: "no-store",
      }
    );
    return redirect("/providers?oauth=success");
  } catch (error) {
    return redirect(`/providers?oauth=failure&reason=${error}`);
  }
}
