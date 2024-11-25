"use client";

import { InformationCircleIcon } from "@heroicons/react/24/outline";
import {
  NumberInput,
  TextInput,
  Textarea,
  Divider,
  Subtitle,
  Text,
  Button,
  Icon,
  Switch,
  Badge,
} from "@tremor/react";
import { FormEvent, useEffect, useState } from "react";
import { toast } from "react-toastify";
import { ExtractionRule } from "./model";
import { extractNamedGroups } from "./extractions-table";
import { useExtractions } from "utils/hooks/useExtractionRules";
import { AlertsRulesBuilder } from "@/app/(keep)/alerts/alerts-rules-builder";
import { useApi } from "@/shared/lib/hooks/useApi";

interface Props {
  extractionToEdit: ExtractionRule | null;
  editCallback: (rule: ExtractionRule | null) => void;
}

export default function CreateOrUpdateExtractionRule({
  extractionToEdit,
  editCallback,
}: Props) {
  const api = useApi();
  const { mutate } = useExtractions();
  const [extractionName, setExtractionName] = useState<string>("");
  const [isPreFormatting, setIsPreFormatting] = useState<boolean>(false);
  const [mapDescription, setMapDescription] = useState<string>("");
  const [condition, setCondition] = useState<string>("");
  const [attribute, setAttribute] = useState<string>("");
  const [regex, setRegex] = useState<string>("");
  const [extractedAttributes, setExtractedAttributes] = useState<string[]>([]);
  const [priority, setPriority] = useState<number>(0);
  const editMode = extractionToEdit !== null;

  useEffect(() => {
    if (regex) {
      const extracted = extractNamedGroups(regex);
      setExtractedAttributes(extracted);
    }
  }, [regex]);

  useEffect(() => {
    if (extractionToEdit) {
      setExtractionName(extractionToEdit.name);
      setMapDescription(extractionToEdit.description ?? "");
      setPriority(extractionToEdit.priority);
      setIsPreFormatting(extractionToEdit.pre);
      setAttribute(extractionToEdit.attribute);
      setRegex(extractionToEdit.regex);
      setCondition(extractionToEdit.condition ?? "");
    }
  }, [extractionToEdit]);

  const clearForm = () => {
    setExtractionName("");
    setMapDescription("");
    setPriority(0);
    setIsPreFormatting(false);
    setRegex("");
    setAttribute("");
    setCondition("");
    setExtractedAttributes([]);
  };

  const addExtraction = async (e: FormEvent) => {
    e.preventDefault();
    const response = await api.post("/extraction", {
      priority: priority,
      name: extractionName,
      description: mapDescription,
      pre: isPreFormatting,
      attribute: attribute,
      regex: regex,
      condition: condition,
    });
    if (response.ok) {
      exitEditOrCreateMode();
      clearForm();
      mutate();
      toast.success("Extraction rule created successfully");
    } else {
      toast.error(
        "Failed to create extraction rule, please contact us if this issue persists."
      );
    }
  };

  // This is the function that will be called on submitting the form in the editMode, it sends a PUT request to the backennd.
  const updateExtraction = async (e: FormEvent) => {
    e.preventDefault();
    const response = await api.put(`/extraction/${extractionToEdit?.id}`, {
      priority: priority,
      name: extractionName,
      description: mapDescription,
      pre: isPreFormatting,
      attribute: attribute,
      regex: regex,
      condition: condition,
    });
    if (response.ok) {
      exitEditOrCreateMode();
      mutate();
      toast.success("Extraction updated successfully");
    } else {
      toast.error(
        "Failed to update extraction, please contact us if this issue persists."
      );
    }
  };

  const exitEditOrCreateMode = async () => {
    editCallback(null);
    clearForm();
  };

  const submitEnabled = (): boolean => {
    return (
      !!extractionName &&
      extractedAttributes.length > 0 &&
      !!regex &&
      !!attribute
    );
  };

  return (
    <form
      className="py-2"
      onSubmit={editMode ? updateExtraction : addExtraction}
    >
      <Subtitle>Extraction Metadata</Subtitle>
      <div className="mt-2.5">
        <Text>
          Name<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder="Extraction Name"
          required={true}
          value={extractionName}
          onValueChange={setExtractionName}
        />
      </div>
      <div className="mt-2.5">
        <Text>Description</Text>
        <Textarea
          placeholder="Extraction Description"
          value={mapDescription}
          onValueChange={setMapDescription}
        />
      </div>
      <div className="mt-2.5">
        <Text>
          Priority
          <Icon
            icon={InformationCircleIcon}
            size="xs"
            color="gray"
            tooltip="Higher priority will be executed first"
          />
        </Text>
        <NumberInput
          placeholder="Priority"
          required={true}
          value={priority}
          onValueChange={setPriority}
          min={0}
          max={100}
        />
      </div>
      <div className="mt-2.5">
        <Text>
          Pre-formatting
          <Icon
            icon={InformationCircleIcon}
            size="xs"
            color="gray"
            tooltip="Whether this rule should be applied before or after the alert is standardized."
          />
        </Text>
        <Switch checked={isPreFormatting} onChange={setIsPreFormatting} />
      </div>
      <Divider />
      <Subtitle className="mt-2.5">
        <div className="flex items-center">
          Extraction Definition{" "}
          <a
            href="https://docs.keephq.dev/overview/enrichment/extraction"
            target="_blank"
          >
            <Icon
              icon={InformationCircleIcon}
              variant="simple"
              color="gray"
              size="sm"
              tooltip="See extractions documentation for more information"
            />
          </a>
        </div>
      </Subtitle>
      <div className="mt-2.5">
        <Text>
          Attribute<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder="Event attribute name to extract from"
          required={true}
          value={attribute}
          onValueChange={setAttribute}
        />
      </div>
      <div className="mt-2.5">
        <Text>
          Regex<span className="text-red-500 text-xs">*</span>
          <a
            href="https://docs.python.org/3.11/library/re.html#match-objects"
            target="_blank"
          >
            <Icon
              icon={InformationCircleIcon}
              size="xs"
              color="gray"
              tooltip="Python regex pattern for group matching"
            />
          </a>
        </Text>
        <TextInput
          placeholder="The regex rule to extract by"
          required={true}
          value={regex}
          error={extractedAttributes.length === 0 && regex !== ""}
          errorMessage="Invalid regex pattern. Must contain named groups."
          onValueChange={setRegex}
        />
      </div>
      <div className="mt-2.5">
        <Text>
          Condition
          <a href="https://docs.keephq.dev/overview/presets" target="_blank">
            <Icon
              icon={InformationCircleIcon}
              variant="simple"
              color="gray"
              size="xs"
              tooltip="CEL based condition"
            />
          </a>
        </Text>
        <div className="mb-5">
          <AlertsRulesBuilder
            defaultQuery={condition}
            updateOutputCEL={setCondition}
            showSave={false}
            showSqlImport={false}
            showToast={true}
            shouldSetQueryParam={false}
          />
        </div>
      </div>
      <div className="mt-2.5">
        <Text>Extracted Attributes</Text>
        <Text className="text-xs">
          (I.e., attributes that will be added to matching incoming events)
        </Text>
        <div className="flex flex-col gap-1 py-1">
          {extractedAttributes.length === 0 ? (
            <Badge color="gray">...</Badge>
          ) : (
            extractedAttributes.map((attribute) => (
              <Badge key={attribute} color="orange">
                {attribute}
              </Badge>
            ))
          )}
        </div>
      </div>
      <div className={"space-x-1 flex flex-row justify-end items-center"}>
        <Button
          color="orange"
          size="xs"
          variant="secondary"
          onClick={exitEditOrCreateMode}
        >
          Cancel
        </Button>
        <Button
          disabled={!submitEnabled()}
          color="orange"
          size="xs"
          type="submit"
        >
          {editMode ? "Update" : "Create"}
        </Button>
      </div>
    </form>
  );
}
