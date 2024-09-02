import SSOSettings from "./sso-settings";

interface Props {
  accessToken: string;
}

export default function SSOSubTab({ accessToken }: Props) {
  return <SSOSettings accessToken={accessToken} selectedTab="sso" />;
}
