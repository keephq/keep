import APIKeySettings from "./api-key-settings";

interface Props {
  accessToken: string;
}

export default function APIKeysSubTab({ accessToken }: Props) {
  return <APIKeySettings accessToken={accessToken} selectedTab="api-key" />;
}
