import { Dialog } from "@headlessui/react";
import { useState } from "react";
import {
  TextInput,
  Button,
  Subtitle,
  Icon,
  SearchSelect,
  SearchSelectItem,
} from "@tremor/react";
import { AuthenticationType } from "utils/authenticationType";
import { User } from "./models";
import { getApiURL } from "utils/apiUrl";
import { InfoCircledIcon } from "@radix-ui/react-icons";
import "./add-user-modal.css";

interface RoleOption {
  value: string;
  label: string | JSX.Element;
  tooltip?: string;
  isDisabled?: boolean;
}

interface AddUserModalProps {
  isOpen: boolean;
  onClose: () => void;
  authType: string;
  setUsers: React.Dispatch<React.SetStateAction<User[]>>;
  accessToken: string;
}

const roleOptions: RoleOption[] = [
  {
    value: "admin",
    label: "Admin",
    tooltip: "Admin has read/write/update/delete for every resource",
  },
  {
    value: "noc",
    label: "NOC",
    tooltip: "NOC has the ability to view and assign alerts",
  },
  {
    value: "create_new",
    label: "Create custom role",
    isDisabled: true,
    tooltip: "For custom roles, contact Keep team",
  },
];

export default function AddUserModal({
  isOpen,
  onClose,
  authType,
  setUsers,
  accessToken,
}: AddUserModalProps) {
  const [email, setEmail] = useState("");
  const [emailError, setEmailError] = useState("");
  const [selectedRole, setSelectedRole] = useState<string>();
  const [password, setPassword] = useState("");
  const [addUserError, setAddUserError] = useState("");

  const validateEmail = (email: string) => {
    const re = /\S+@\S+\.\S+/;
    return re.test(email);
  };

  const isFormValid = () => {
    // if multi tenant, we need to validate email, else just validate password
    if (authType === AuthenticationType.MULTI_TENANT) {
      return validateEmail(email) && selectedRole;
    } else {
      return email && selectedRole && password;
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate form
    if (!isFormValid()) {
      setAddUserError("Please fill out all fields");
      return;
    }
    // Validate selected role
    if (!selectedRole) {
      setAddUserError("Please select a role");
      return;
    }

    // Make the API call to add the user
    const response = await fetch(`${getApiURL()}/settings/users`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, role: selectedRole, password }),
    });

    if (response.ok) {
      const newUser = await response.json();
      setUsers((currentUsers) => [...currentUsers, newUser]);
      // Reset form and close modal on successful addition
      handleOnClose();
    } else {
      const errorData = await response.json();
      setAddUserError(
        errorData.message ||
          errorData.detail ||
          "Failed to add user (unknown error)"
      );
    }
  };

  const handleOnClose = () => {
    onClose();
    setEmail("");
    setSelectedRole("");
    setPassword("");
    setAddUserError("");
  };

  const handleEmailChange = (email: string) => {
    setEmail(email);
    if (validateEmail(email)) {
      setEmailError("");
    } else {
      setEmailError("Please enter a valid email address.");
    }
  };

  return (
    <Dialog
      as="div"
      className="fixed inset-0 z-10 overflow-y-auto"
      open={isOpen}
      onClose={handleOnClose}
    >
      <div className="flex items-center justify-center min-h-screen">
        <Dialog.Panel
          className="bg-white p-4 rounded"
          style={{ width: "400px", maxWidth: "90%" }}
        >
          <Dialog.Title>Add User</Dialog.Title>
          <form onSubmit={handleSubmit}>
            {/* If authType is email, user email, otherwise just username */}
            {authType === AuthenticationType.MULTI_TENANT ? (
              <div className="mt-4">
                <Subtitle>Email</Subtitle>
                <TextInput
                  value={email}
                  onChange={(e) => handleEmailChange(e.target.value)}
                  error={!!emailError && !!email}
                  errorMessage={emailError}
                />
              </div>
            ) : (
              <div className="mt-4">
                <Subtitle>Username</Subtitle>
                <TextInput
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            )}

            <div className="mt-4">
              <Subtitle>Role</Subtitle>
              <SearchSelect
                value={selectedRole}
                onValueChange={(val) => setSelectedRole(val)}
                className="mt-2"
                placeholder="Select role"
              >
                {roleOptions.map((role) => (
                  <SearchSelectItem
                    key={role.value}
                    value={role.value}
                    className={
                      role.isDisabled ? "text-gray-400 cursor-not-allowed" : ""
                    }
                    onClick={(e) => {
                      if (role.isDisabled) {
                        e.preventDefault();
                      }
                    }}
                  >
                    <div className="flex items-center">
                      {role.label}
                      {role.tooltip && (
                        <Icon
                          icon={InfoCircledIcon}
                          className="role-tooltip"
                          tooltip={role.tooltip}
                          color="gray"
                          size="xs"
                        />
                      )}
                    </div>
                  </SearchSelectItem>
                ))}
              </SearchSelect>
            </div>

            {authType === AuthenticationType.SINGLE_TENANT && (
              <div className="mt-4">
                <Subtitle>Password</Subtitle>
                <TextInput
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>
            )}
            {addUserError && (
              <div className="text-red-500 mt-2">{addUserError}</div> // Display error message
            )}
            <div className="mt-6 flex gap-2">
              <Button color="orange" type="submit" disabled={!isFormValid()}>
                Add User
              </Button>
              <Button
                onClick={handleOnClose}
                variant="secondary"
                className="border border-orange-500 text-orange-500"
              >
                Cancel
              </Button>
            </div>
          </form>
        </Dialog.Panel>
      </div>
    </Dialog>
  );
}
