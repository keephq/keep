import React, { useState, useEffect } from "react";
import {
  Badge,
  Card,
  Subtitle,
  Title,
  Text,
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
  Button,
  TextInput,
  Textarea,
} from "@tremor/react";
import { useDroppable } from "@dnd-kit/core";
import {
  SortableContext,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { AlertDto } from "@/entities/alerts/model";
import { IncidentCandidateDto } from "@/entities/incidents/model";

interface IncidentCardProps {
  incident: IncidentCandidateDto;
  index: number;
  onIncidentChange: (updatedIncident: IncidentCandidateDto) => void;
}

interface EditableField {
  name: keyof IncidentCandidateDto;
  label: string;
  type: "text" | "textarea";
}

const editableFields: EditableField[] = [
  { name: "name", label: "Incident Name", type: "text" },
  { name: "description", label: "Description", type: "textarea" },
  { name: "confidence_score", label: "Confidence Score", type: "text" },
  {
    name: "confidence_explanation",
    label: "Confidence Explanation",
    type: "textarea",
  },
];

interface DraggableAlertRowProps {
  alert: AlertDto;
  alertIndex: number;
  incidentIndex: number;
}

const DraggableAlertRow: React.FC<DraggableAlertRowProps> = ({
  alert,
  alertIndex,
  incidentIndex,
}) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({
    id: alert.fingerprint,
    data: {
      type: "alert",
      alertIndex,
      incidentIndex,
    },
  });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
    cursor: "grab",
    touchAction: "none",
  };

  return (
    <TableRow
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className={`${isDragging ? "bg-gray-50" : ""} hover:bg-gray-50 transition-colors`}
    >
      <TableCell className="w-1/6 break-words">
        {alert.name || "Unnamed Alert"}
      </TableCell>
      <TableCell className="w-2/3 break-words whitespace-normal">
        {alert.description || "No description"}
      </TableCell>
      <TableCell className="w-1/12 break-words">
        {alert.severity || "N/A"}
      </TableCell>
      <TableCell className="w-1/12 break-words">
        {alert.status || "N/A"}
      </TableCell>
    </TableRow>
  );
};

const DroppableContainer: React.FC<{
  id: string;
  children: React.ReactNode;
}> = ({ id, children }) => {
  const { setNodeRef, isOver } = useDroppable({
    id,
    data: {
      type: "container",
      accepts: "alert",
      incidentIndex: id,
    },
  });

  return (
    <div
      ref={setNodeRef}
      className={`transition-colors ${isOver ? "bg-orange-50" : ""}`}
    >
      {children}
    </div>
  );
};

const IncidentCard: React.FC<IncidentCardProps> = ({
  incident,
  index,
  onIncidentChange,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedIncident, setEditedIncident] =
    useState<IncidentCandidateDto>(incident);

  useEffect(() => {
    if (incident) {
      setEditedIncident(incident);
    }
  }, [incident]);

  const handleEditToggle = () => {
    setIsEditing(!isEditing);
    if (isEditing && editedIncident) {
      onIncidentChange(editedIncident);
    }
  };

  const handleFieldChange = (
    field: keyof IncidentCandidateDto,
    value: string
  ) => {
    setEditedIncident((prev) => {
      if (!prev) return prev;
      return { ...prev, [field]: value };
    });
  };

  const renderEditableField = (field: EditableField) => {
    if (!editedIncident) return null;

    const value = editedIncident[field.name] as string;
    return (
      <div key={field.name} className="mb-4">
        <label className="block text-sm font-medium text-gray-700">
          {field.label}
        </label>
        {field.type === "textarea" ? (
          <Textarea
            value={value || ""}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            className="mt-1"
          />
        ) : (
          <TextInput
            value={value || ""}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            className="mt-1"
          />
        )}
      </div>
    );
  };

  if (!editedIncident) return null;

  return (
    <Card key={incident.id} className="mb-6 relative">
      <div className="absolute top-4 right-4">
        <Button onClick={handleEditToggle}>
          {isEditing ? "Save Changes" : "Edit Incident"}
        </Button>
      </div>
      {isEditing ? (
        <div className="mt-12">{editableFields.map(renderEditableField)}</div>
      ) : (
        <>
          <Title>{editedIncident.name || "Unnamed Incident"}</Title>
          <Subtitle className="mt-2">Description</Subtitle>
          <Text className="mt-2">
            {editedIncident.description || "No description"}
          </Text>
          <Subtitle className="mt-2">Severity</Subtitle>
          <Badge color="orange">{editedIncident.severity || "N/A"}</Badge>
          <Subtitle className="mt-2">Confidence Score</Subtitle>
          <Text>{editedIncident.confidence_score || "N/A"}</Text>
          <Subtitle className="mt-2">Confidence Explanation</Subtitle>
          <Text>
            {editedIncident.confidence_explanation || "No explanation"}
          </Text>
        </>
      )}
      <DroppableContainer id={index.toString()}>
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell className="w-1/6">Alert Name</TableHeaderCell>
              <TableHeaderCell className="w-2/3">Description</TableHeaderCell>
              <TableHeaderCell className="w-1/12">Severity</TableHeaderCell>
              <TableHeaderCell className="w-1/12">Status</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            <SortableContext
              items={(editedIncident.alerts || []).map((a) => a.fingerprint)}
              strategy={verticalListSortingStrategy}
            >
              {(editedIncident.alerts || []).map(
                (alert: AlertDto, alertIndex: number) => (
                  <DraggableAlertRow
                    key={alert.fingerprint}
                    alert={alert}
                    alertIndex={alertIndex}
                    incidentIndex={index}
                  />
                )
              )}
            </SortableContext>
          </TableBody>
        </Table>
      </DroppableContainer>
    </Card>
  );
};

export default IncidentCard;
