import UsersSettings from "./users-settings";
import { User as AuthUser } from "next-auth";

interface Props {
  accessToken: string;
  currentUser?: AuthUser;
  groupsAllowed: boolean;
}

export default function UserTab({ accessToken, currentUser, groupsAllowed }: Props) {
  return (
    <UsersSettings
      accessToken={accessToken}
      currentUser={currentUser}
      groupsAllowed={groupsAllowed}
      selectedTab="users"
    />
  );
}
