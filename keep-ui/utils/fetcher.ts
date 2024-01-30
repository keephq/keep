export const fetcher = async (url: string, accessToken: string | undefined) => {
  const response = await fetch(url, {
    headers: {
      Authorization: `Bearer ${accessToken}`,
    },
  });

  // Ensure that the fetch was successful
  if (!response.ok) {
    throw new Error("An error occurred while fetching the data.");
  }

  // Parse and return the JSON data
  return response.json();
};
