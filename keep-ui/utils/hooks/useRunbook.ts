import useSWR, { SWRConfiguration } from "swr";
import { getRunBookUrl } from "utils/apiUrl";
import { fetcher, OverideHeaders } from "utils/fetcher";
import { useProviders } from "./useProviders";
import { ProvidersResponse, Provider } from "app/providers/providers";
import { useCallback, useEffect, useMemo, useState } from "react";
import { debounce } from "lodash";

export const useRunBookTriggers = (values: any) => {
  const providersData = useProviders();
  const [error, setError] = useState("");
  const [synced, setSynced] = useState(false);
  const [fileData, setFileData] = useState<any>([]);
  const [reposData, setRepoData] = useState<any>([]);
  const { pathToMdFile, repoName, userName, providerId, domain } = values || {};
  const { installed_providers, providers } = (providersData?.data ||
    {}) as ProvidersResponse;
  const runBookInstalledProviders =
    installed_providers?.filter((provider) =>
      ["github", "gitlab"].includes(provider.type)
    ) || [];
  const provider = runBookInstalledProviders?.find(
    (provider) => provider.id === providerId
  );

  const apiUrl = getRunBookUrl(provider!);

  function getAccessToken(provider: Provider) {
    switch (provider?.type) {
      case "github":
        return provider?.details?.authentication?.access_token;
      case "gitlab":
        return (
          provider?.details?.authentication?.personal_access_token ||
          provider?.details?.authentication?.access_token
        );
      default:
        return "";
    }
  }

  const accessToken = getAccessToken(provider!);

  function constructRepoUrl() {
    switch (provider?.type) {
      case "github":
        return `${apiUrl}/users/${userName}/repos`;
      case "gitlab":
        return `${apiUrl}/users/${userName}/projects`;
      default:
        return "";
    }
  }

  useEffect(() => {
    const getUserRepos = async () => {
      if (!userName) {
        return setRepoData([]);
      }
      const url = constructRepoUrl();
      if (!url) {
        return setRepoData([]);
      }
      try {
        //need to move it backend.
        const data = await fetcher(url, accessToken);
        setRepoData(data);
      } catch (err) {
        console.log("error occurred while fetching data");
        setRepoData([]);
      }
    };

    const debounceUserReposRequest = debounce(getUserRepos, 400);
    debounceUserReposRequest();

    // Cleanup to cancel the debounce on unmount or before the next effect run
    return () => {
      debounceUserReposRequest.cancel();
    };
  }, [userName, apiUrl, provider?.id]);

  function constructUrl(
    userName: string,
    repoName: string,
    pathToMdFile: string
  ) {
    switch (provider?.type) {
      case "github":
        return `${apiUrl}/repos/${userName}/${repoName}/contents/${pathToMdFile}`;
      case "gitlab":
        const repoId = reposData?.find(
          (repo: any) => repo.name === repoName
        )?.id;
        return `${apiUrl}/projects/${repoId}/repository/files/${pathToMdFile}?ref=main`;
      default:
        return "";
    }
  }

  function constructHeaders() {
    switch (provider?.type) {
      case "gitlab":
        return {
          headers: {
            "PRIVATE-TOKEN": accessToken,
          },
        } as OverideHeaders;
      default:
        return {} as OverideHeaders;
    }
  }

  const handleSubmit = async (data: any) => {
    const { pathToMdFile, repoName, userName } = data;
    if (!pathToMdFile) {
      return { loading: false, data: [], error: "User name is required" };
    }

    const url = constructUrl(userName, repoName, pathToMdFile);
    if (!url) {
      return setError("Url not found");
    }

    const headers = constructHeaders();

    try {
      //need to move to backend.
      const response = await fetcher(url, accessToken, {}, headers);

      if (!response) {
        return setError("Something went wrong. try agian after some time");
      }

      setFileData(response);
      setSynced(false);
      //send it to backend and store the details in db. to DO
    } catch (err) {
      return setError("Something went wrong. try agian after some time");
    } finally {
      setSynced(true);
    }
  };

  const HandlePreview = () => {};

  return {
    runBookInstalledProviders,
    providersData,
    reposData,
    handleSubmit,
    fileData,
    HandlePreview,
  };
};
