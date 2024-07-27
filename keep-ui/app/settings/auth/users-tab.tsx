import UsersSettings from "./users-settings";
import { User as AuthUser } from "next-auth";

interface Props {
  accessToken: string;
  currentUser?: AuthUser;
}

export default function UserTab({ accessToken, currentUser }: Props) {
  return (
    <UsersSettings
      accessToken={accessToken}
      currentUser={currentUser}
      selectedTab="users"
    />
  );
}
