"use client";

import { MagnifyingGlassIcon } from "@radix-ui/react-icons";
import {
  NumberInput,
  TextInput,
  Textarea,
  Divider,
  Subtitle,
  Text,
  MultiSelect,
  MultiSelectItem,
  Badge,
  Button,
} from "@tremor/react";
import { useSession } from "next-auth/react";
import { ChangeEvent, FormEvent, useMemo, useState } from "react";
import { usePapaParse } from "react-papaparse";
import { toast } from "react-toastify";
import { getApiURL } from "utils/apiUrl";
import { useMappings } from "utils/hooks/useMappingRules";

export default function CreateNewMapping() {
  const { data: session } = useSession();
  const { mutate } = useMappings();
  const [mapName, setMapName] = useState<string>("");
  const [fileName, setFileName] = useState<string>("");
  const [mapDescription, setMapDescription] = useState<string>("");
  const [selectedAttributes, setSelectedAttributes] = useState<string[]>([]);
  const [priority, setPriority] = useState<number>(0);

  /** This is everything related with the uploaded CSV file */
  const [parsedData, setParsedData] = useState<any[] | null>(null);
  const attributes = useMemo(() => {
    if (parsedData) {
      return Object.keys(parsedData[0]);
    }
    return [];
  }, [parsedData]);
  const { readString } = usePapaParse();

  const readFile = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    setFileName(file?.name || "");
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result;
      if (typeof text === "string") {
        readString(text, {
          header: true,
          complete: (results) => {
            if (results.data.length > 0) setParsedData(results.data);
          },
        });
      }
    };
    if (file) reader.readAsText(file);
  };

  const clearForm = () => {
    setMapName("");
    setMapDescription("");
    setParsedData(null);
    setSelectedAttributes([]);
  };

  const addRule = async (e: FormEvent) => {
    e.preventDefault();
    const apiUrl = getApiURL();
    const response = await fetch(`${apiUrl}/mapping`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session?.accessToken}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        priority: priority,
        name: mapName,
        description: mapDescription,
        file_name: fileName,
        matchers: selectedAttributes,
        rows: parsedData,
      }),
    });
    if (response.ok) {
      clearForm();
      mutate();
      toast.success("Mapping created successfully");
    } else {
      toast.error(
        "Failed to create mapping, please contact us if this issue persists."
      );
    }
  };

  const submitEnabled = (): boolean => {
    return (
      !!mapName &&
      selectedAttributes.length > 0 &&
      !!parsedData &&
      attributes.filter(
        (attribute) => selectedAttributes.includes(attribute) === false
      ).length > 0
    );
  };

  return (
    <form className="max-w-lg py-2" onSubmit={addRule}>
      <Subtitle>Mapping Metadata</Subtitle>
      <div className="mt-2.5">
        <Text>
          Priority<span className="text-red-500 text-xs">*</span>
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
          Name<span className="text-red-500 text-xs">*</span>
        </Text>
        <TextInput
          placeholder="Map Name"
          required={true}
          value={mapName}
          onValueChange={setMapName}
        />
      </div>
      <div className="mt-2.5">
        <Text>Description</Text>
        <Textarea
          placeholder="Map Description"
          value={mapDescription}
          onValueChange={setMapDescription}
        />
      </div>
      <Divider />
      <div>
        <input
          type="file"
          accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
          onChange={readFile}
          required={true}
        />
        {!parsedData && (
          <Text className="text-xs text-red-500">
            * Upload a CSV file to begin with creating a new mapping
          </Text>
        )}
      </div>
      <Subtitle className="mt-2.5">Mapping Schema</Subtitle>
      <div className="mt-2.5">
        <Text>Alert lookup attributes to match against the uploaded CSV</Text>
        <Text className="text-xs">
          (E.g. the attributes that we will try to match before enriching)
        </Text>
        <MultiSelect
          className="mt-1"
          value={selectedAttributes}
          onValueChange={setSelectedAttributes}
          disabled={!parsedData}
          icon={MagnifyingGlassIcon}
        >
          {attributes &&
            attributes.map((attribute) => (
              <MultiSelectItem key={attribute} value={attribute}>
                {attribute}
              </MultiSelectItem>
            ))}
        </MultiSelect>
      </div>
      <div className="mt-2.5">
        <Text>Result attributes</Text>
        <Text className="text-xs">
          (E.g. attributes that will be added to matching incoming alerts)
        </Text>
        <div className="flex flex-col gap-1 py-1">
          {selectedAttributes.length === 0 ? (
            <Badge color="gray">...</Badge>
          ) : (
            attributes
              .filter(
                (attribute) => selectedAttributes.includes(attribute) === false
              )
              .map((attribute) => (
                <Badge key={attribute} color="orange">
                  {attribute}
                </Badge>
              ))
          )}
        </div>
      </div>
      <Button
        disabled={!submitEnabled()}
        color="orange"
        size="xs"
        className="float-right"
        type="submit"
      >
        Create
      </Button>
    </form>
  );
}
