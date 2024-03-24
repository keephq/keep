import React, { useState } from "react";
import { AlertDto, Preset } from "./models";
import Modal from "@/components/ui/Modal";
import { Button, TextInput } from "@tremor/react";
import { getApiURL } from "utils/apiUrl";
import { toast } from "react-toastify";
import { useSession } from "next-auth/react";
import { usePresets } from "utils/hooks/usePresets";
import { useRouter } from "next/navigation";
import { Table } from "@tanstack/react-table";
import { AlertsRulesBuilder } from "./alerts-rules-builder";

interface Props {
  preset: Preset | null;
  isLoading: boolean;
  table: Table<AlertDto>;
}

export default function AlertPresets({ preset, isLoading, table }: Props) {
  const apiUrl = getApiURL();
  const { useAllPresets } = usePresets();
  const { mutate: presetsMutator, data: savedPresets = [] } = useAllPresets({
    revalidateOnFocus: false,
  });
  const { data: session } = useSession();
  const router = useRouter();

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [presetName, setPresetName] = useState(
    preset?.name === "feed" || preset?.name === "deleted" ? "" : preset?.name
  );
  const [isPrivate, setIsPrivate] = useState(preset?.is_private);
  const [presetCEL, setPresetCEL] = useState("");

  const selectedPreset = savedPresets.find(
    (savedPreset) =>
      savedPreset.name.toLowerCase() ===
      decodeURIComponent(preset!.name).toLowerCase()
  ) as Preset | undefined;

  async function deletePreset(presetId: string) {
    if (
      confirm(`You are about to delete preset ${preset!.name}, are you sure?`)
    ) {
      const response = await fetch(`${apiUrl}/preset/${presetId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session?.accessToken}`,
        },
      });
      if (response.ok) {
        toast(`Preset ${preset!.name} deleted!`, {
          position: "top-left",
          type: "success",
        });
        presetsMutator();
        router.push("/alerts/feed");
      }
    }
  }

  async function addOrUpdatePreset() {
    if (presetName) {
      const response = await fetch(
        selectedPreset?.id
          ? `${apiUrl}/preset/${selectedPreset?.id}`
          : `${apiUrl}/preset`,
        {
          method: selectedPreset?.id ? "PUT" : "POST",
          headers: {
            Authorization: `Bearer ${session?.accessToken}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            name: presetName,
            options: [
              {
                label: "CEL",
                value: presetCEL,
              },
            ],
            is_private: isPrivate,
          }),
        }
      );
      if (response.ok) {
        setIsModalOpen(false);
        toast(
          selectedPreset?.name
            ? `Preset ${presetName} updated!`
            : `Preset ${presetName} created!`,
          {
            position: "top-left",
            type: "success",
          }
        );
        await presetsMutator();
        router.push(`/alerts/${presetName.toLowerCase()}`);
      }
    }
  }

  return (
    <>
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        className="w-[30%] max-w-screen-2xl max-h-[710px] transform overflow-auto ring-tremor bg-white p-6 text-left align-middle shadow-tremor transition-all rounded-xl"
      >
        <div className="space-y-2">
          <div className="text-lg font-semibold">
            <p>
              {presetName ? "Update preset name?" : "Enter new preset name"}
            </p>
          </div>

          <div className="space-y-2">
            <TextInput
              error={!presetName}
              errorMessage="Preset name is required"
              placeholder={
                presetName === "feed" || presetName === "deleted"
                  ? ""
                  : presetName
              }
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              className="w-full"
            />
          </div>

          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id={"private"}
              checked={isPrivate}
              onChange={() => setIsPrivate(!isPrivate)}
            />
            <label htmlFor={"private"}>Private</label>
          </div>

          <div className="flex justify-end space-x-2.5">
            <Button
              size="lg"
              variant="secondary"
              color="orange"
              onClick={() => setIsModalOpen(false)}
              tooltip="Close Modal"
            >
              Close
            </Button>
            <Button
              size="lg"
              color="orange"
              onClick={addOrUpdatePreset}
              tooltip="Save Modal"
            >
              Save
            </Button>
          </div>
        </div>
      </Modal>
      <div className="flex w-full items-start mt-6">
        <AlertsRulesBuilder
          table={table}
          defaultQuery=""
          selectedPreset={selectedPreset}
          setIsModalOpen={setIsModalOpen}
          deletePreset={deletePreset}
          setPresetCEL={setPresetCEL}
        />
      </div>
    </>
  );
}
