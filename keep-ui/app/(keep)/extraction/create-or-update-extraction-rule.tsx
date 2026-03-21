"use client";
import { useI18n } from "@/i18n/hooks/useI18n";

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
import { useExtractions } from "utils/hooks/useExtractionRules";
import { AlertsRulesBuilder } from "@/features/presets/presets-manager";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import { useConfig } from "@/utils/hooks/useConfig";
import { extractNamedGroups } from "@/shared/lib/regex-utils";

interface Props {
  extractionToEdit: ExtractionRule | null;
  editCallback: (rule: ExtractionRule | null) => void;
}

export default function CreateOrUpdateExtractionRule({
  extractionToEdit,
  editCallback,
}: Props) {
  const { t } = useI18n();
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
  const { data: config } = useConfig();

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
    try {
      const response = await api.post("/extraction", {
        priority: priority,
        name: extractionName,
        description: mapDescription,
        pre: isPreFormatting,
        attribute: attribute,
        regex: regex,
        condition: condition,
      });
      exitEditOrCreateMode();
      clearForm();
      mutate();
      toast.success(t("rules.extraction.messages.createSuccess"));
    } catch (error) {
      showErrorToast(error, t("rules.extraction.messages.createFailed"));
    }
  };

  // This is the function that will be called on submitting the form in the editMode, it sends a PUT request to the backennd.
  const updateExtraction = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const response = await api.put(`/extraction/${extractionToEdit?.id}`, {
        priority: priority,
        name: extractionName,
        description: mapDescription,
        pre: isPreFormatting,
        attribute: attribute,
        regex: regex,
        condition: condition,
      });
      exitEditOrCreateMode();
      mutate();
      toast.success(t("rules.extraction.messages.updateSuccess"));
    } catch (error) {
      showErrorToast(error, t("rules.extraction.messages.updateFailed"));
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
      className="py-2 h-full overflow-y-auto"
      onSubmit={editMode ? updateExtraction : addExtraction}
    >
      <Subtitle>{t("rules.extraction.form.metadata")}</Subtitle>
      <div className="mt-2.5">
        <Text>
          {t("rules.extraction.form.name")}<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder={t("rules.extraction.form.placeholders.extractionName")}
          required={true}
          value={extractionName}
          onValueChange={setExtractionName}
        />
      </div>
      <div className="mt-2.5">
        <Text>{t("rules.extraction.form.description")}</Text>
        <Textarea
          placeholder={t("rules.extraction.form.placeholders.extractionDescription")}
          value={mapDescription}
          onValueChange={setMapDescription}
        />
      </div>
      <div className="mt-2.5">
        <Text>
          {t("rules.extraction.form.priority")}
          <Icon
            icon={InformationCircleIcon}
            size="xs"
            color="gray"
            tooltip={t("rules.extraction.form.priorityTooltip")}
          />
        </Text>
        <NumberInput
          placeholder={t("rules.extraction.form.placeholders.priority")}
          required={true}
          value={priority}
          onValueChange={setPriority}
          min={0}
          max={100}
        />
      </div>
      <div className="mt-2.5">
        <Text>
          {t("rules.extraction.form.preFormatting")}
          <Icon
            icon={InformationCircleIcon}
            size="xs"
            color="gray"
            tooltip={t("rules.extraction.form.preFormattingTooltip")}
          />
        </Text>
        <Switch checked={isPreFormatting} onChange={setIsPreFormatting} />
      </div>
      <Divider />
      <Subtitle className="mt-2.5 flex items-center">
        {t("rules.extraction.form.extractionDefinition")}{" "}
        <a
          href={`${
            config?.KEEP_DOCS_URL || "https://docs.keephq.dev"
          }/overview/enrichment/extraction`}
          target="_blank"
        >
          <Icon
            icon={InformationCircleIcon}
            variant="simple"
            color="gray"
            size="sm"
            tooltip={t("rules.extraction.form.extractionDefinitionTooltip")}
          />
        </a>
      </Subtitle>
      <div className="mt-2.5">
        <Text>
          {t("rules.extraction.form.attribute")}<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder={t("rules.extraction.form.placeholders.attribute")}
          required={true}
          value={attribute}
          onValueChange={setAttribute}
        />
      </div>
      <div className="mt-2.5">
        <Text>
          {t("rules.extraction.form.regex")}<span className="text-red-500 text-xs">*</span>
          <a
            href="https://docs.python.org/3.11/library/re.html#match-objects"
            target="_blank"
          >
            <Icon
              icon={InformationCircleIcon}
              size="xs"
              color="gray"
              tooltip={t("rules.extraction.form.regexTooltip")}
            />
          </a>
        </Text>
        <TextInput
          placeholder={t("rules.extraction.form.placeholders.regex")}
          required={true}
          value={regex}
          error={extractedAttributes.length === 0 && regex !== ""}
          errorMessage={t("rules.extraction.form.regexError")}
          onValueChange={setRegex}
        />
      </div>
      <div className="mt-2.5">
        <Text>
          {t("rules.extraction.form.condition")}
          <a
            href={`${
              config?.KEEP_DOCS_URL || "https://docs.keephq.dev"
            }/overview/presets`}
            target="_blank"
          >
            <Icon
              icon={InformationCircleIcon}
              variant="simple"
              color="gray"
              size="xs"
              tooltip={t("rules.extraction.form.conditionTooltip")}
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
        <Text>{t("rules.extraction.form.extractedAttributes")}</Text>
        <Text className="text-xs">
          {t("rules.extraction.form.extractedAttributesDescription")}
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
          {t("common.actions.cancel")}
        </Button>
        <Button
          disabled={!submitEnabled()}
          color="orange"
          size="xs"
          type="submit"
        >
          {editMode ? t("common.actions.update") : t("common.actions.create")}
        </Button>
      </div>
    </form>
  );
}
