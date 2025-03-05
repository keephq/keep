import { useState } from "react";
import { Button, Text } from "@tremor/react";
import { useApi } from "@/shared/lib/hooks/useApi";
import { showErrorToast } from "@/shared/ui";
import Modal from "@/components/ui/Modal";
import { Select } from "@/shared/ui";
import { useProviderImages } from "@/entities/provider-images/model/useProviderImages";

interface Props {
  providers: string[];
  isOpen: boolean;
  onClose: () => void;
  onUploadComplete: () => Promise<void>;
  customImages: Array<{ provider_name: string }>;
}

export function ProviderImageUploader({
  providers,
  customImages,
  isOpen,
  onClose,
  onUploadComplete,
}: Props) {
  const api = useApi();
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [selectedProvider, setSelectedProvider] = useState<string>("");
  const [isUploading, setIsUploading] = useState(false);

  const providerOptions = providers.map((provider) => ({
    value: provider,
    label: provider,
  }));

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // Check if file is a PNG
    if (file.type !== "image/png") {
      showErrorToast(new Error("Please select a PNG image file"));
      event.target.value = ""; // Clear the input
      return;
    }

    setSelectedFile(file);
  };

  const handleUpload = async () => {
    if (!selectedFile || !selectedProvider) return;

    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.set("file", selectedFile);

      await api.request(`/provider-images/upload/${selectedProvider}`, {
        method: "POST",
        body: formData,
      });

      await onUploadComplete();
    } catch (error) {
      showErrorToast(error);
    } finally {
      setIsUploading(false);
    }
  };

  const handleClose = () => {
    setSelectedFile(null);
    setSelectedProvider("");
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Upload Provider Image">
      <div className="space-y-6">
        <div>
          <Text className="mb-2">Select Provider</Text>
          <Select
            value={providerOptions.find(
              (option) => option.value === selectedProvider
            )}
            onChange={(option) => setSelectedProvider(option?.value || "")}
            options={providerOptions}
            placeholder="Select a provider"
          />
        </div>

        <div>
          <Text className="mb-2">Upload PNG Image</Text>
          <input
            type="file"
            accept="image/png"
            onChange={handleFileSelect}
            className="block w-full text-sm text-gray-500
              file:mr-4 file:py-2 file:px-4
              file:rounded-full file:border-0
              file:text-sm file:font-semibold
              file:bg-orange-50 file:text-orange-700
              hover:file:bg-orange-100"
          />
          <Text className="mt-1 text-xs text-gray-500">
            Only PNG files are supported
          </Text>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" color="orange" onClick={handleClose}>
            Cancel
          </Button>
          <Button
            color="orange"
            onClick={handleUpload}
            disabled={!selectedFile || !selectedProvider || isUploading}
          >
            {isUploading ? "Uploading..." : "Upload"}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
