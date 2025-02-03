import React, { useMemo, useState } from "react";
import { AlertDto } from "@/entities/alerts/model";
import Modal from "@/components/ui/Modal";
import { useRouter } from "next/navigation";
import { Table } from "@tanstack/react-table";
import { AlertsRulesBuilder } from "./alerts-rules-builder";
import { CreateOrUpdatePresetForm } from "@/features/create-or-update-preset";
import { STATIC_PRESETS_NAMES } from "@/entities/presets/model/constants";
import { Preset } from "@/entities/presets/model/types";
import { usePresets } from "@/entities/presets/model/usePresets";
import { CopilotKit } from "@copilotkit/react-core";

interface Props {
  presetName: string;
  // TODO: pass specific functions not the whole table?
  table?: Table<AlertDto>;
  onCelChanges?: (cel: string) => void;
}

export function AlertPresetManager({ presetName, table, onCelChanges }: Props) {
  const { dynamicPresets } = usePresets({
    revalidateOnFocus: false,
  });
  // TODO: make a hook for this? store in the context?
  const selectedPreset = useMemo(() => {
    return dynamicPresets?.find(
      (p) =>
        p.name.toLowerCase() === decodeURIComponent(presetName).toLowerCase()
    ) as Preset | undefined;
  }, [dynamicPresets, presetName]);
  const [presetCEL, setPresetCEL] = useState("");

  // modal
  const [isModalOpen, setIsModalOpen] = useState(false);
  const router = useRouter();

  const onCreateOrUpdatePreset = (preset: Preset) => {
    setIsModalOpen(false);
    const encodedPresetName = encodeURIComponent(preset.name.toLowerCase());
    router.push(`/alerts/${encodedPresetName}`);
  };

  const handleModalClose = () => {
    setIsModalOpen(false);
  };

  const isDynamic =
    selectedPreset && !STATIC_PRESETS_NAMES.includes(selectedPreset.name);

  // Static presets are not editable
  const idToUpdate = isDynamic ? selectedPreset.id : null;

  const presetData = isDynamic
    ? {
        CEL: presetCEL,
        name: selectedPreset.name,
        isPrivate: selectedPreset.is_private,
        isNoisy: selectedPreset.is_noisy,
        tags: selectedPreset.tags,
      }
    : {
        CEL: presetCEL,
        name: undefined,
        isPrivate: undefined,
        isNoisy: undefined,
        tags: undefined,
      };

  return (
    <>
      <div className="flex w-full items-start relative z-10">
        <AlertsRulesBuilder
          table={table}
          defaultQuery=""
          selectedPreset={selectedPreset}
          setIsModalOpen={setIsModalOpen}
          setPresetCEL={setPresetCEL}
          onCelChanges={onCelChanges}
        />
      </div>
      <Modal
        isOpen={isModalOpen}
        onClose={handleModalClose}
        className="w-[40%] max-w-screen-2xl max-h-[710px] transform overflow-auto ring-tremor bg-white p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
      >
        <CopilotKit runtimeUrl="/api/copilotkit">
          <CreateOrUpdatePresetForm
            key={idToUpdate}
            presetId={idToUpdate}
            presetData={presetData}
            onCreateOrUpdate={onCreateOrUpdatePreset}
            onCancel={handleModalClose}
          />
        </CopilotKit>
      </Modal>
    </>
  );
}
