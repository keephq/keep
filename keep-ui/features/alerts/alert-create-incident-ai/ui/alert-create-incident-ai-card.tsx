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
import { FormattedContent } from "@/shared/ui/FormattedContent/FormattedContent";
import { useI18n } from "@/i18n/hooks/useI18n";

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

const getEditableFields = (t: (key: string) => string): EditableField[] => [
  { name: "name", label: t("alerts.createIncidentAI.incidentName"), type: "text" },
  { name: "description", label: t("common.labels.description"), type: "textarea" },
  { name: "confidence_score", label: t("alerts.createIncidentAI.confidenceScore"), type: "text" },
  {
    name: "confidence_explanation",
    label: t("alerts.createIncidentAI.confidenceExplanation"),
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
  const { t } = useI18n();
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
      className={`${
        isDragging ? "bg-gray-50" : ""
      } hover:bg-gray-50 transition-colors`}
    >
      <TableCell className="w-1/6 break-words">
        {alert.name || t("alerts.createIncidentAI.unnamedAlert")}
      </TableCell>
      <TableCell className="w-2/3 break-words whitespace-normal">
        <FormattedContent
          content={alert.description || t("alerts.createIncidentAI.noDescription")}
          format={alert.description_format}
        />
      </TableCell>
      <TableCell className="w-1/12 break-words">
        {alert.severity || t("common.messages.notApplicable")}
      </TableCell>
      <TableCell className="w-1/12 break-words">
        {alert.status || t("common.messages.notApplicable")}
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
  const { t } = useI18n();
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
          {isEditing ? t("alerts.createIncidentAI.saveChanges") : t("alerts.createIncidentAI.editIncident")}
        </Button>
      </div>
      {isEditing ? (
        <div className="mt-12">{getEditableFields(t).map(renderEditableField)}</div>
      ) : (
        <>
          <Title>{editedIncident.name || t("alerts.createIncidentAI.unnamedIncident")}</Title>
          <Subtitle className="mt-2">{t("common.labels.description")}</Subtitle>
          <Text className="mt-2">
            <FormattedContent
              content={editedIncident.description || t("alerts.createIncidentAI.noDescription")}
              format={editedIncident.description_format}
            />
          </Text>
          <Subtitle className="mt-2">{t("common.labels.severity")}</Subtitle>
          <Badge color="orange">{editedIncident.severity || t("common.messages.notApplicable")}</Badge>
          <Subtitle className="mt-2">{t("alerts.createIncidentAI.confidenceScore")}</Subtitle>
          <Text>{editedIncident.confidence_score || t("common.messages.notApplicable")}</Text>
          <Subtitle className="mt-2">{t("alerts.createIncidentAI.confidenceExplanation")}</Subtitle>
          <Text>
            {editedIncident.confidence_explanation || t("alerts.createIncidentAI.noExplanation")}
          </Text>
        </>
      )}
      <DroppableContainer id={index.toString()}>
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell className="w-1/6">{t("alerts.createIncidentAI.alertName")}</TableHeaderCell>
              <TableHeaderCell className="w-2/3">{t("common.labels.description")}</TableHeaderCell>
              <TableHeaderCell className="w-1/12">{t("common.labels.severity")}</TableHeaderCell>
              <TableHeaderCell className="w-1/12">{t("common.labels.status")}</TableHeaderCell>
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
