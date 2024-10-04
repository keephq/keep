import { Session } from "next-auth";
import { fetcher } from "@/utils/fetcher";
import { getApiURL } from "@/utils/apiUrl";

export interface Pagination {
  limit: number;
  offset: number;
}

export const defaultPagination: Pagination = {
  limit: 20,
  offset: 0,
};

export const defaultSorting = [{ id: "creation_time", desc: true }];

export function fetchIncidents(
  session: Session | null = null,
  confirmed: boolean = true,
  limit: number = 25,
  offset: number = 0,
  sorting: { id: string; desc: boolean } = { id: "creation_time", desc: false }
) {
  if (!session) {
    return null;
  }
  return fetcher(
    `${getApiURL()}/incidents?confirmed=${confirmed}&limit=${limit}&offset=${offset}&sorting=${
      sorting.desc ? "-" : ""
    }${sorting.id}`,
    session?.accessToken
  );
}
