import {
  Title,
  Subtitle,
  Card,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
  Text,
  Button,
  MultiSelect,
  MultiSelectItem,
  Badge,
  TextInput,
  Callout
} from "@tremor/react";
import Loading from "app/loading";
import { useState, useEffect } from "react";
import { useConfig } from "utils/hooks/useConfig";
import { getApiURL } from "utils/apiUrl";
import { useScopes } from "utils/hooks/useScopes";
import { useRoles } from "utils/hooks/useRoles";
import Modal from "@/components/ui/Modal";
import { useForm, Controller, SubmitHandler, FieldValues } from "react-hook-form";
import React from "react";
import "./multiselect.css";
import { TrashIcon } from "@heroicons/react/24/outline";

interface Props {
  accessToken: string;
}

interface ScopeMatrix {
  read: boolean;
  write: boolean;
  delete: boolean;
  update: boolean;
}


export default function RolesTab({ accessToken }: Props) {
  const apiUrl = getApiURL();
  const { data: configData } = useConfig();
  const { data: scopes = [] , isLoading: scopesLoading, error: scopesError } = useScopes();
  const { data: roles = [], isLoading: rolesLoading, error: rolesError, mutate: mutateRoles } = useRoles();

  const [resources, setResources] = useState<string[]>([]);
  const [roleStates, setRoleStates] = useState<{ [key: string]: { scopes: string[] } }>({});
  const [hasChanges, setHasChanges] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newRoleScopes, setNewRoleScopes] = useState<{ [key: string]: ScopeMatrix }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [hoveredRole, setHoveredRole] = useState<string | null>(null);

  const { control, handleSubmit, reset, formState: { errors }, setError, clearErrors } = useForm();

  useEffect(() => {
    if (scopes) {
      const extractedResources = [...new Set(scopes.map(scope => scope.split(':')[1]).filter(resource => resource !== '*'))];
      setResources(extractedResources);
    }
  }, [scopes]);

  useEffect(() => {
    if (roles  && roles.length > 0) {
      const initialRoleStates = roles.reduce((acc, role) => {
        acc[role.name] = {
          scopes: role.scopes || [],
        };
        return acc;
      }, {} as { [key: string]: { scopes: string[] } });
      setRoleStates(initialRoleStates);
    }
  }, [roles]);

  if (scopesLoading || rolesLoading) return <Loading />;

  const expandedScopes = scopes.flatMap((scope) => {
    if (scope.includes(":*")) {
      const [action] = scope.split(":");
      return resources.map((resource) => `${action}:${resource}`);
    }
    return [scope];
  });

  const handleScopeChange = (roleId: string, newScopes: string[]) => {
    setRoleStates((prevStates) => ({
      ...prevStates,
      [roleId]: {
        ...prevStates[roleId],
        scopes: newScopes,
      },
    }));
    setHasChanges(true);
  };

  const handleNewRoleScopeChange = (resource: string, action: keyof ScopeMatrix) => {
    setNewRoleScopes((prev) => ({
      ...prev,
      [resource]: {
        ...prev[resource],
        [action]: !prev[resource]?.[action],
      },
    }));
  };

  const updateRoles = async () => {
    // Implement the logic to update roles and their scopes
    console.log("Updating role states:", roleStates);
    await mutateRoles();
    setHasChanges(false);
  };

  const deleteRole = async (roleName: string) => {
    // Implement the logic to delete a role
    console.log("Deleting role:", roleName);
    await mutateRoles();
  }

  const onSubmit: SubmitHandler<FieldValues> = async (data) => {
    setIsSubmitting(true);
    clearErrors();
    try {
      const newRole = { ...data, scopes: Object.entries(newRoleScopes)
        .filter(([_, actions]) => Object.values(actions).some(Boolean))
        .flatMap(([resource, actions]) =>
          Object.entries(actions)
            .filter(([_, value]) => value)
            .map(([action, _]) => `${action}:${resource}`)
        )
      };

      const response = await fetch(`${apiUrl}/auth/roles`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(newRole),
      });

      if (response.ok) {
        console.log("Saving new role:", newRole);
        setNewRoleScopes({});
        reset();
        setIsModalOpen(false);
        await mutateRoles();
      } else {
        const errorData = await response.json();
        if (errorData.detail) {
          setError("apiError", { type: "manual", message: errorData.detail });
        } else {
          setError("apiError", {
            type: "manual",
            message: errorData.message || "Failed to add role",
          });
        }
      }
    } catch (error) {
      setError("apiError", {
        type: "manual",
        message: "An unexpected error occurred",
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="mt-10 h-full flex flex-col">
      <div className="flex justify-between mb-4">
        <div className="flex flex-col">
          <Title>Roles Management</Title>
          <Subtitle>Manage user roles</Subtitle>
        </div>
        <div className="flex space-x-2">
          <Button
            color="orange"
            size="md"
            variant="secondary"
            onClick={() => {
              clearErrors();
              reset();
              setIsModalOpen(true);
            }}
          >
            Add Role
          </Button>
          <Button
            color="orange"
            size="md"
            onClick={updateRoles}
            disabled={!hasChanges}
          >
            Update Roles
          </Button>
        </div>
      </div>
      <Card className="flex-grow overflow-auto h-full">
        <Table className="h-full">
          <TableHead>
            <TableRow>
              <TableHeaderCell className="w-1/6">Role Name</TableHeaderCell>
              <TableHeaderCell className="w-1/6">Description</TableHeaderCell>
              <TableHeaderCell className="w-2/3">Scopes</TableHeaderCell>
              <TableHeaderCell className="w-1/12"></TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {roles
              .sort((a, b) => {
                if (a.predefined === b.predefined) return 0;
                return a.predefined ? -1 : 1;
              })
              .map((role) => (
                <TableRow
                  key={role.name}
                  className="hover:bg-gray-50 transition-colors duration-200"
                  onMouseEnter={() => setHoveredRole(role.name)}
                  onMouseLeave={() => setHoveredRole(null)}
                >
                  <TableCell className="w-1/6">
                    <div className="flex items-center justify-between">
                      <Text className="truncate">{role.name}</Text>
                      {role.predefined ? (
                        <Badge color="orange" className="ml-2 w-24 text-center">Predefined</Badge>
                      ) : (
                        <Badge color="orange" className="ml-2 w-24 text-center">Custom</Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="w-1/6">
                    <Text>{role.description}</Text>
                  </TableCell>
                  <TableCell className="text-right w-2/3">
                    <div className="flex items-center justify-between">
                      <div className="max-h-60 flex-grow">
                        <MultiSelect
                          placeholder="Select scopes"
                          className="custom-multiselect"
                          value={roleStates[role.name]?.scopes || []}
                          onValueChange={(value) => handleScopeChange(role.name, value)}
                          disabled={role.predefined}
                        >
                          {expandedScopes.map((scope) => (
                            <MultiSelectItem
                              key={scope}
                              value={scope}
                            >
                              {scope}
                            </MultiSelectItem>
                          ))}
                        </MultiSelect>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="w-1/12">
                    {!role.predefined && hoveredRole === role.name && (
                      <Button
                        icon={TrashIcon}
                        color="orange"
                        title="Delete role"
                        onClick={async () => await deleteRole(role.name)}
                        className="ml-2"
                        size="xs"
                      ></Button>
                    )}
                  </TableCell>
                </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>
      <Modal isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} title="Add Role" className="w-[600px]">
        <div className="relative bg-white p-6 rounded-lg">
          <form onSubmit={(e) => {
            clearErrors();
            handleSubmit(onSubmit)(e);
          }} className="mt-4">
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700">
                Role Name
              </label>
              <Controller
                name="name"
                control={control}
                rules={{ required: "Role name is required" }}
                render={({ field }) => (
                  <TextInput
                    {...field}
                    error={!!errors.name}
                    errorMessage={errors.name?.message}
                  />
                )}
              />
            </div>
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700">
                Description
              </label>
              <Controller
                name="description"
                control={control}
                rules={{ required: "Description is required" }}
                render={({ field }) => (
                  <TextInput
                    {...field}
                    error={!!errors.description}
                    errorMessage={errors.description?.message}
                  />
                )}
              />
            </div>
            <div className="mt-4">
              <Text>Scopes</Text>
              <div className="grid grid-cols-5 gap-4 mt-2">
                <div></div>
                <Text>Read</Text>
                <Text>Write</Text>
                <Text>Delete</Text>
                <Text>Update</Text>
                {resources.map((resource) => (
                  <React.Fragment key={resource}>
                    <Text>{resource}</Text>
                    {["read", "write", "delete", "update"].map((action) => (
                      <div
                        key={action}
                        className={`flex items-center justify-center cursor-pointer ${
                          newRoleScopes[resource]?.[action] ? 'text-green-500' : 'text-gray-300'
                        }`}
                        onClick={() => handleNewRoleScopeChange(resource, action as keyof ScopeMatrix)}
                      >
                        {newRoleScopes[resource]?.[action] ? (
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        ) : (
                          <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                          </svg>
                        )}
                      </div>
                    ))}
                  </React.Fragment>
                ))}
              </div>
            </div>
            {/* Display API Error */}
            {errors.apiError && typeof errors.apiError.message === "string" && (
              <Callout
                className="mt-4"
                title="Error while adding role"
                color="rose"
              >
                {errors.apiError.message}
              </Callout>
            )}
            <div className="mt-6 flex justify-end gap-2">
              <Button
                color="orange"
                variant="secondary"
                onClick={() => setIsModalOpen(false)}
                className="border border-orange-500 text-orange-500"
              >
                Cancel
              </Button>
              <Button
                color="orange"
                type="submit"
                disabled={isSubmitting || !newRoleScopes || !Object.values(newRoleScopes).some(scope => Object.values(scope).some(Boolean))}
                title={
                  !newRoleScopes
                    ? "At least one scope must be selected"
                    : ""
                }
              >
                {isSubmitting ? "Saving..." : "Save Role"}
              </Button>
            </div>
          </form>
        </div>
      </Modal>
    </div>
  );
}
