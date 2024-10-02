import useSWR, { SWRConfiguration } from "swr";
import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useProviders } from "./useProviders";
import { ProvidersResponse, Provider } from "app/providers/providers";
import { useEffect, useState } from "react";
import { debounce } from "lodash";
import { useSession } from "next-auth/react";
import { toast } from "react-toastify";

export const useRunBookTriggers = (values: any, refresh: number) => {
  const providersData = useProviders();
  const [error, setError] = useState("");
  const [synced, setSynced] = useState(false);
  const [fileData, setFileData] = useState<any>({});
  const [reposData, setRepoData] = useState<any>([]);
  const { pathToMdFile, repoName, userName, providerId, domain } = values || {};
  const { data: session } = useSession();
  const { installed_providers, providers } = (providersData?.data ||
    {}) as ProvidersResponse;
  const runBookInstalledProviders =
    installed_providers?.filter((provider) =>
      ["github", "gitlab"].includes(provider.type)
    ) || [];
  const provider = runBookInstalledProviders?.find(
    (provider) => provider.id === providerId && providerId
  );

  const baseApiurl = getApiURL();

  useEffect(() => {
    const getUserRepos = async () => {
      try {
        if(!provider) {
          return setRepoData([]);
        }
        const data = await fetcher(
          `${baseApiurl}/providers/${provider?.type}/${provider?.id}/repositories`,
          session?.accessToken
        );
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
  }, [refresh]);

  const handleSubmit = async (data: any) => {
    const { pathToMdFile, repoName } = data;
    try {
      if(!provider){
        return toast("Please select a provider");
      }
      const params = new URLSearchParams();
      if (pathToMdFile) {
        params.append("md_path", pathToMdFile);
      }
      if (repoName) {
        params.append("repo", repoName);
      }
      //TO DO backend runbook records needs to be created.
      const response = await fetcher(
        `${baseApiurl}/providers/${provider?.type}/${
          provider?.id
        }/runbook?${params.toString()}`,
        session?.accessToken
      );

      if (!response) {
        return setError("Something went wrong. try agian after some time");
      }
      setFileData(response);
      setSynced(false);
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
    provider,
  };
};
