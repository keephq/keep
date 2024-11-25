import { auth } from "@/auth";
import { getConfig } from "../server/getConfig";
import { ApiClient } from "./ApiClient";

export async function getServerApiClient() {
  const session = await auth();
  const config = getConfig();
  return new ApiClient(session, config, true);
}
