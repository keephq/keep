import { providerMap } from "@/auth";
import { CredentialsSignInForm } from "./CredentialsSignInForm";
import "../../../globals.css";

export type SignInFormPageProps = {
  params: {
    amt: string;
  };
  searchParams: {
    callbackUrl?: string;
  };
};

export default async function SignInFormPage({
  params,
  searchParams,
}: SignInFormPageProps) {
  if (
    providerMap.get("credentials") &&
    providerMap.get("credentials") != "NoAuth"
  ) {
    console.log(
      "Signing in with credentials provider",
      providerMap.get("credentials")
    );
    return (
      <CredentialsSignInForm params={params} searchParams={searchParams} />
    );
  }

  return <>Error</>;
}
