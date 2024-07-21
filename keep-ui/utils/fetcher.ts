export const fetcher = async (
  url: string,
  accessToken: string | undefined,
  requestInit: RequestInit = {}
) => {
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
    ...requestInit,
  });

  // Ensure that the fetch was successful
  if (!response.ok) {
    // if the response has detail field, throw the detail field
    if (response.headers.get("content-type")?.includes("application/json")) {
      const data = await response.json();
      throw new Error(`An error occurred while fetching the data. ${data.message}`);
    }
    throw new Error("An error occurred while fetching the data.");
  }

  // Parse and return the JSON data
  return response.json();
};
