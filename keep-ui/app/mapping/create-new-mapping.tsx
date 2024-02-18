"use client";

import { MagnifyingGlassIcon } from "@radix-ui/react-icons";
import {
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
import { ChangeEvent, FormEvent, useMemo, useState } from "react";
import { usePapaParse } from "react-papaparse";

export default function CreateNewMapping() {
  const [mapName, setMapName] = useState<string>("");
  const [mapDescription, setMapDescription] = useState<string>("");
  const [selectedAttributes, setSelectedAttributes] = useState<string[]>([]);

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

  const addRule = async (e: FormEvent) => {
    e.preventDefault();
    const ruleData = parsedData?.reduce((acc, row) => {
      const copiedRow = { ...row };
      // attribute=attributeValue&&attribute2=attribute2Value
      const key = selectedAttributes.reduce((key, attribute, index) => {
        key += `${attribute}=${copiedRow[attribute]}`;
        if (index !== selectedAttributes.length - 1) key += "&&";
        delete copiedRow[attribute];
        return key;
      }, "");
      return { ...acc, [key]: copiedRow };
    }, {});
    console.log(ruleData);
  };

  const submitEnabled = (): boolean => {
    return !!mapName && selectedAttributes.length > 0 && !!parsedData;
  };

  return (
    <form className="max-w-lg py-2" onSubmit={addRule}>
      <Subtitle>Mapping Metadata</Subtitle>
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
      <input
        type="file"
        accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel"
        onChange={readFile}
      />
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
        Submit
      </Button>
    </form>
  );
}
