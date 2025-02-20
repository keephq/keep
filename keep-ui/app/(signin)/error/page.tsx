// app/error/page.tsx
import ErrorClient from "./error-client";
import { getAuthTypeEnvVars } from "./authEnvUtils";

export default function ErrorPage({
  searchParams,
}: {
  searchParams: { error?: string; status?: string };
}) {
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
