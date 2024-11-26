import { redirect } from "next/navigation";
import { cookies } from "next/headers";
import { createServerApiClient } from "@/shared/lib/api/createServerApiClient";

export default async function InstallFromOAuth({
  params,
  searchParams,
}: {
  params: { providerType: string };
  searchParams: { [key: string]: string };
}) {
  const api = await createServerApiClient();
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
  } catch (error: unknown) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    return redirect(
      `/providers?oauth=failure&reason=${encodeURIComponent(errorMessage)}`
    );
  }
}
