// app/error/page.tsx
import ErrorClient from "./error-client";
import { getAuthTypeEnvVars } from "./authEnvUtils";

export default async function ErrorPage(
  props: {
    searchParams: Promise<{ error?: string; status?: string }>;
  }
) {
  const searchParams = await props.searchParams;
  const authType = process.env.AUTH_TYPE;
  const authEnvVars = getAuthTypeEnvVars(authType);

  return (
    <ErrorClient
      error={searchParams.error || null}
      status={searchParams.status}
      authType={authType}
      authEnvVars={authEnvVars}
    />
  );
}
