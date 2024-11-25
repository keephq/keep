import { InternalConfig } from "@/types/internal-config";
import { Session } from "next-auth";
import { KeepApiError } from "./KeepApiError";
import { getApiUrlFromConfig } from "./getApiUrlFromConfig";
import { getApiURL } from "@/utils/apiUrl";

export class ApiClient {
  constructor(
    private readonly session: Session | null,
    private readonly config: InternalConfig | null,
    private readonly isServer: boolean
  ) {}

  isReady() {
    return !!this.session && !!this.config;
  }

  getHeaders() {
    if (!this.session) {
      throw new Error("No session found");
    }
    return {
      Authorization: `Bearer ${this.session.accessToken}`,
    };
  }

  async handleResponse(response: Response, url: string) {
    // Ensure that the fetch was successful
    if (!response.ok) {
      // if the response has detail field, throw the detail field
      if (response.headers.get("content-type")?.includes("application/json")) {
        const data = await response.json();
        if (response.status === 401) {
          throw new KeepApiError(
            `${data.message || data.detail}`,
            url,
            `You probably just need to sign in again.`,
            data,
            response.status
          );
        }
        throw new KeepApiError(
          `${data.message || data.detail}`,
          url,
          `Please try again. If the problem persists, please contact support.`,
          data,
          response.status
        );
      }
      throw new Error("An error occurred while fetching the data.");
    }

    try {
      return await response.json();
    } catch (error) {
      console.error(error);
      return response.text();
    }
  }

  async fetch(url: string, requestInit: RequestInit = {}) {
    const apiUrl = this.isServer
      ? getApiURL()
      : getApiUrlFromConfig(this.config);
    const fullUrl = apiUrl + url;

    if (!this.config) {
      throw new Error("No config found");
    }

    const response = await fetch(fullUrl, {
      ...requestInit,
      headers: {
        ...this.getHeaders(),
        ...requestInit.headers,
      },
    });
    return this.handleResponse(response, url);
  }

  async get(url: string, requestInit: RequestInit = {}) {
    return this.fetch(url, { method: "GET", ...requestInit });
  }

  async post(
    url: string,
    data?: any,
    { headers, ...requestInit }: RequestInit = {}
  ) {
    return this.fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: data ? JSON.stringify(data) : undefined,
      ...requestInit,
    });
  }

  async put(
    url: string,
    data?: any,
    { headers, ...requestInit }: RequestInit = {}
  ) {
    return this.fetch(url, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: data ? JSON.stringify(data) : undefined,
      ...requestInit,
    });
  }

  async patch(
    url: string,
    data?: any,
    { headers, ...requestInit }: RequestInit = {}
  ) {
    return this.fetch(url, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: data ? JSON.stringify(data) : undefined,
      ...requestInit,
    });
  }

  async delete(
    url: string,
    data?: any,
    { headers, ...requestInit }: RequestInit = {}
  ) {
    return this.fetch(url, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
        ...headers,
      },
      body: data ? JSON.stringify(data) : undefined,
      ...requestInit,
    });
  }
}
