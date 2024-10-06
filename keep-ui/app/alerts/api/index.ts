import { getApiURL } from "@/utils/apiUrl";
import { fetcher } from "@/utils/fetcher";
import { Session } from "next-auth";

export function fetchAllAlertsForPreset(
  session: Session | null,
  preset: string
) {
  if (!session) {
    return null;
  }
  return fetcher(
    `${getApiURL()}/preset/${preset}/alerts`,
    session?.accessToken
  );
}
