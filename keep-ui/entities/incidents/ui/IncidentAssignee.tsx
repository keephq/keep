import React, { useState } from "react";
import { User } from "@/app/(keep)/settings/models";
import { useUsers } from "@/entities/users/model/useUsers";
import { useIncidentActions } from "@/entities/incidents/model";
import { Select } from "@/shared/ui/Select/Select";

interface Props {
  assignee: string | null;
  incidentId: string;
  className?: string;
  optionColor?: string;
}

export function IncidentAssignee({
  assignee,
  incidentId,
  className,
  optionColor,
}: Props) {
  const { data: users, isLoading } = useUsers();
  const { updateIncident } = useIncidentActions();
  const [isUpdating, setIsUpdating] = useState(false);

  const handleAssigneeChange = async (option: any) => {
    setIsUpdating(true);
    try {
      await updateIncident(
        incidentId,
        { assignee: option.value === "unassigned" ? null : option.value },
        false
      );
    } catch (error) {
      console.error("Failed to update assignee:", error);
    } finally {
      setIsUpdating(false);
    }
  };

  if (isLoading) {
    return (
      <div className={`flex items-center gap-2 ${className}`}>
        <span className="text-gray-400">Assignee</span>
        <div className="animate-pulse bg-gray-200 h-6 w-24 rounded"></div>
      </div>
    );
  }

  const options = [
    {
      value: "unassigned",
      label: "Unassigned",
      logoUrl: "/anonymous-avatar.svg", // Add your anonymous avatar path here
    },
    ...(users?.map((user) => ({
      value: user.email,
      label: user.email,
      logoUrl: user.picture || undefined,
    })) || []),
  ];

  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <span className="text-gray-400">Assignee</span>
      <Select
        value={options.find(
          (option) => option.value === (assignee || "unassigned")
        )}
        onChange={handleAssigneeChange}
        isDisabled={isUpdating || !users?.length}
        className="min-w-[100px]"
        options={options}
        backgroundColor="rgb(229 231 235)"
        optionColor={optionColor}
      />
    </div>
  );
}
