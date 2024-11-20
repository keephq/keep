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
import { Droppable, Draggable } from "react-beautiful-dnd";
import { AlertDto } from "./models";
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

const IncidentCard: React.FC<IncidentCardProps> = ({
  incident,
  index,
  onIncidentChange,
}) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedIncident, setEditedIncident] =
    useState<IncidentCandidateDto>(incident);

  useEffect(() => {
    setEditedIncident(incident);
  }, [incident]);

  const handleEditToggle = () => {
    setIsEditing(!isEditing);
    if (isEditing) {
      onIncidentChange(editedIncident);
    }
  };

  const handleFieldChange = (
    field: keyof IncidentCandidateDto,
    value: string
  ) => {
    setEditedIncident((prev) => ({ ...prev, [field]: value }));
  };

  const renderEditableField = (field: EditableField) => {
    const value = editedIncident[field.name] as string;
    return (
      <div key={field.name} className="mb-4">
        <label className="block text-sm font-medium text-gray-700">
          {field.label}
        </label>
        {field.type === "textarea" ? (
          <Textarea
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            className="mt-1"
          />
        ) : (
          <TextInput
            value={value}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
            className="mt-1"
          />
        )}
      </div>
    );
  };

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
          <Title>{editedIncident.name}</Title>
          <Subtitle className="mt-2">Description</Subtitle>
          <Text className="mt-2">{editedIncident.description}</Text>
          <Subtitle className="mt-2">Severity</Subtitle>
          <Badge color="orange">{editedIncident.severity}</Badge>
          <Subtitle className="mt-2">Confidence Score</Subtitle>
          <Text>{editedIncident.confidence_score}</Text>
          <Subtitle className="mt-2">Confidence Explanation</Subtitle>
          <Text>{editedIncident.confidence_explanation}</Text>
        </>
      )}
      <Droppable droppableId={index.toString()}>
        {(provided: any) => (
          <div {...provided.droppableProps} ref={provided.innerRef}>
            <Table>
              <TableHead>
                <TableRow>
                  <TableHeaderCell className="w-1/6">
                    Alert Name
                  </TableHeaderCell>
                  <TableHeaderCell className="w-2/3">
                    Description
                  </TableHeaderCell>
                  <TableHeaderCell className="w-1/12">Severity</TableHeaderCell>
                  <TableHeaderCell className="w-1/12">Status</TableHeaderCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {editedIncident.alerts.map(
                  (alert: AlertDto, alertIndex: number) => (
                    <Draggable
                      key={alert.fingerprint}
                      draggableId={alert.fingerprint}
                      index={alertIndex}
                    >
                      {(provided: any) => (
                        <TableRow
                          ref={provided.innerRef}
                          {...provided.draggableProps}
                          {...provided.dragHandleProps}
                        >
                          <TableCell className="w-1/6 break-words">
                            {alert.name}
                          </TableCell>
                          <TableCell className="w-2/3 break-words whitespace-normal">
                            {alert.description}
                          </TableCell>
                          <TableCell className="w-1/12 break-words">
                            {alert.severity}
                          </TableCell>
                          <TableCell className="w-1/12 break-words">
                            {alert.status}
                          </TableCell>
                        </TableRow>
                      )}
                    </Draggable>
                  )
                )}
              </TableBody>
            </Table>
            {provided.placeholder}
          </div>
        )}
      </Droppable>
    </Card>
  );
};

export default IncidentCard;
