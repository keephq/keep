import React, { useMemo, useState } from "react";
import { AlertDto } from "./models";
import Modal from "@/components/ui/Modal";
import { useRouter } from "next/navigation";
import { Table } from "@tanstack/react-table";
import { AlertsRulesBuilder } from "./alerts-rules-builder";
import { CreateOrUpdatePresetForm } from "@/features/create-or-update-preset";
import { usePresetActions } from "@/entities/presets/model/usePresetActions";
import { STATIC_PRESETS_NAMES } from "@/entities/presets/model/constants";
import { Preset } from "@/entities/presets/model/types";
import { usePresets } from "@/entities/presets/model/usePresets";

interface Props {
  presetNameFromApi: string;
  table: Table<AlertDto>;
  presetPrivate?: boolean;
  presetNoisy?: boolean;
}

export default function AlertPresets({ presetNameFromApi, table }: Props) {
  const { deletePreset } = usePresetActions();
  const { dynamicPresets } = usePresets({
    revalidateOnFocus: false,
  });
  // TODO: make a hook for this? store in the context?
  const selectedPreset = useMemo(() => {
    return dynamicPresets?.find(
      (p) =>
        p.name.toLowerCase() ===
        decodeURIComponent(presetNameFromApi).toLowerCase()
    ) as Preset | undefined;
  }, [dynamicPresets, presetNameFromApi]);
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
          deletePreset={deletePreset}
          setPresetCEL={setPresetCEL}
        />
      </div>
      <Modal
        isOpen={isModalOpen}
        onClose={handleModalClose}
        className="w-[40%] max-w-screen-2xl max-h-[710px] transform overflow-auto ring-tremor bg-white p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
      >
        <CreateOrUpdatePresetForm
          key={idToUpdate}
          presetId={idToUpdate}
          presetData={presetData}
          onCreateOrUpdate={onCreateOrUpdatePreset}
          onCancel={handleModalClose}
        />
      </Modal>
    </>
  );
}
