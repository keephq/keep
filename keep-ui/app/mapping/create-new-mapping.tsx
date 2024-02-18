"use client";

import {
  TextInput,
  Textarea,
  Divider,
  Subtitle,
  Text,
  Select,
  SelectItem,
  Badge,
  Button,
} from "@tremor/react";
import { ChangeEvent, FormEvent, useMemo, useState } from "react";
import { usePapaParse } from "react-papaparse";

export default function CreateNewMapping() {
  const [mapName, setMapName] = useState<string>("");
  const [mapDescription, setMapDescription] = useState<string>("");
  const [selectedAttribute, setSelectedAttribute] = useState<string>("");

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
      const key = row[selectedAttribute];
      delete row[selectedAttribute];
      return { ...acc, [key]: row };
    }, {});
    console.log(ruleData);
  };

  const submitEnabled = (): boolean => {
    return !!mapName && !!selectedAttribute && !!parsedData;
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
        <Text>Lookup alert attribute to match against the uploaded CSV</Text>
        <Select
          value={selectedAttribute}
          onValueChange={setSelectedAttribute}
          disabled={!parsedData}
          enableClear={false}
        >
          {attributes &&
            attributes.map((attribute) => (
              <SelectItem key={attribute} value={attribute}>
                {attribute}
              </SelectItem>
            ))}
        </Select>
      </div>
      <div className="mt-2.5">
        <Text>Result attributes</Text>
        <Text>
          (E.g. attributes that will be added to matching incoming alerts)
        </Text>
        <div className="flex flex-col gap-1 py-1">
          {!selectedAttribute ? (
            <Badge color="gray">...</Badge>
          ) : (
            attributes
              .filter((attribute) => attribute !== selectedAttribute)
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
