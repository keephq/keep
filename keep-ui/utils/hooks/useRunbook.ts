import { getApiURL } from "utils/apiUrl";
import { fetcher } from "utils/fetcher";
import { useProviders } from "./useProviders";
import { ProvidersResponse, Provider } from "app/providers/providers";
import { useEffect, useState } from "react";
import { debounce } from "lodash";
import { useSession } from "next-auth/react";
import { toast } from "react-toastify";

export const useRunBookTriggers = (
  values: any,
  refresh: number,
  setIsModalOpen: React.Dispatch<React.SetStateAction<boolean>>
) => {
  const providersData = useProviders();
  const [fileData, setFileData] = useState<any>({});
  const [reposData, setRepoData] = useState<any>([]);
  const { providerId } = values || {};
  const { data: session } = useSession();
  const { installed_providers } = (providersData?.data ||
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
        if (!provider) {
          return setRepoData([]);
        }
        const data = await fetcher(
          `${baseApiurl}/runbooks/${provider?.type}/${provider?.id}/repositories`,
          session?.accessToken
        );
        setRepoData(data);
      } catch (err) {
        console.log("error occurred while fetching data");
        toast.error(
          "Failed to fetch repositories. Please check the provider settings."
        );
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

  const handleSubmit = async (data: any, handleRunbookMutation: () => void) => {
    const { pathToMdFile, repoName, runBookTitle } = data;
    try {
      if (!provider) {
        return toast("Please select a provider");
      }
      const params = new URLSearchParams();
      if (pathToMdFile) {
        params.append("md_path", pathToMdFile);
      }
      if (repoName) {
        params.append("repo", repoName);
      }
      if (runBookTitle) {
        params.append("title", runBookTitle);
      }
      const response = await fetch(
        `${baseApiurl}/runbooks/${provider?.type}/${
          provider?.id
        }?${params.toString()}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session?.accessToken}`,
          },
        }
      );

      if (!response) {
        toast.error(
          "Failed to create runbook. Something went wrong, please try again later."
        );
        return;
      }

      if (!response.ok) {
        toast.error(
          "Failed to create runbook. Something went wrong, please try again later."
        );
        return;
      }

      const result = await response.json();
      setFileData(result);
      setIsModalOpen(false);
      toast.success("Runbook created successfully");
      handleRunbookMutation();
    } catch (err) {
      return;
    } finally {
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
