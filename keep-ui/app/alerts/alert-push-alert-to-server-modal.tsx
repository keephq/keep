import React, { useState, useEffect } from "react";
import {
  Button,
  Textarea,
  Select,
  SelectItem,
  Subtitle,
  Callout,
} from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { useSession } from "next-auth/react";
import { useApiUrl } from "utils/hooks/useConfig";
import { useProviders } from "utils/hooks/useProviders";
import ImageWithFallback from "@/components/ImageWithFallback";
import { useAlerts } from "utils/hooks/useAlerts";
import { usePresets } from "utils/hooks/usePresets";

interface PushAlertToServerModalProps {
  handleClose: () => void;
  presetName: string;
}

interface AlertSource {
  name: string;
  type: string;
  alertExample: string;
}

const PushAlertToServerModal = ({
  handleClose,
  presetName,
}: PushAlertToServerModalProps) => {
  const [alertSources, setAlertSources] = useState<AlertSource[]>([]);
  const [selectedSource, setSelectedSource] = useState<AlertSource | null>(
    null
  );
  const [alertJson, setAlertJson] = useState<string>("");
  const { useAllPresets } = usePresets();
  const { mutate: presetsMutator } = useAllPresets({
    revalidateIfStale: false,
    revalidateOnFocus: false,
  });
  const { usePresetAlerts } = useAlerts();
  const { mutate: mutateAlerts } = usePresetAlerts(presetName);

  const { data: session } = useSession();
  const { data: providersData } = useProviders();
  const apiUrl = useApiUrl();
  const providers = providersData?.providers || [];

  useEffect(() => {
    if (providers) {
      const sources = providers
        .filter((provider) => provider.alertExample)
        .map((provider) => {
          return {
            name: provider.display_name,
            type: provider.type,
            alertExample: JSON.stringify(provider.alertExample, null, 2),
          };
        });
      setAlertSources(sources);
    }
  }, [providers]);

  const handleSourceChange = (value: string) => {
    const source = alertSources.find((source) => source.name === value);
    if (source) {
      setSelectedSource(source);
      setAlertJson(source.alertExample);
    }
  };

  const handleJsonChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setAlertJson(e.target.value);
  };

  const handleSubmit = async () => {
    if (!selectedSource) {
      console.error("No source selected");
      return;
    }

    try {
      const response = await fetch(
        `${apiUrl}/alerts/event/${selectedSource.type}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session?.accessToken}`,
          },
          body: alertJson,
        }
      );

      if (response.ok) {
        console.log("Alert pushed successfully");
        mutateAlerts();
        presetsMutator();
        handleClose();
      } else {
        console.error("Failed to push alert");
      }
    } catch (error) {
      console.error("An unexpected error occurred", error);
    }
  };

  const CustomSelectValue = ({
    selectedSource,
  }: {
    selectedSource: AlertSource;
  }) => (
    <div className="flex items-center">
      <ImageWithFallback
        src={`/icons/${selectedSource.type}-icon.png`}
        fallbackSrc={`/icons/keep-icon.png`}
        width={24}
        height={24}
        alt={selectedSource.type}
        className=""
      />
      <span className="ml-2">{selectedSource.name}</span>
    </div>
  );

  return (
    <Modal
      isOpen={true}
      onClose={handleClose}
      title="Simulate alert"
      className="w-[600px]"
    >
      <div className="relative bg-white p-6 rounded-lg">
        <div className="mt-4">
          <label className="block text-sm font-medium text-gray-700">
            Alert Source
          </label>
          <Select
            value={selectedSource ? selectedSource.name : ""}
            onValueChange={handleSourceChange}
            placeholder="Select alert source"
            className="mt-2"
          >
            {selectedSource && (
              <CustomSelectValue selectedSource={selectedSource} />
            )}
            {alertSources.map((source) => (
              <SelectItem key={source.name} value={source.name}>
                <div className="flex items-center">
                  <ImageWithFallback
                    src={`/icons/${source.type}-icon.png`}
                    fallbackSrc={`/icons/keep-icon.png`}
                    width={32}
                    height={32}
                    alt={source.type}
                    className=""
                  />
                  <span className="ml-2">{source.name.toLowerCase()}</span>
                </div>
              </SelectItem>
            ))}
          </Select>
          <Callout
            title="About alert payload"
            color="orange"
            className="break-words mt-4"
          >
            Feel free to edit the payload as you want. However, some of the
            providers expects specific fields, so be careful.
          </Callout>
        </div>
        {selectedSource && (
          <>
            <div className="mt-4">
              <label className="block text-sm font-medium text-gray-700">
                Alert Payload
              </label>
              <Textarea
                value={alertJson}
                onChange={handleJsonChange}
                rows={20}
                className="w-full mt-1"
              />
            </div>
            <div className="mt-6 flex gap-2">
              <Button color="orange" onClick={handleSubmit}>
                Submit
              </Button>
              <Button
                onClick={handleClose}
                variant="secondary"
                className="border border-orange-500 text-orange-500"
              >
                Cancel
              </Button>
            </div>
          </>
        )}
      </div>
    </Modal>
  );
};

export default PushAlertToServerModal;
