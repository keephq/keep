import React, { useState } from "react";
import { TextInput } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { CreateFacetDto } from "./models";
import { Button } from "@/components/ui";
import { useI18n } from "@/i18n/hooks/useI18n";

interface AddFacetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddFacet: (createFacet: CreateFacetDto) => void;
}

export const AddFacetModal: React.FC<AddFacetModalProps> = ({
  isOpen,
  onClose,
  onAddFacet,
}) => {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [propertyPath, setPropertyPath] = useState("");

  const handleNewFacetCreation = () => {
    onAddFacet({
      property_path: propertyPath,
      name: name,
    });
    close();
  };

  const close = () => {
    setName("");
    setPropertyPath("");
    onClose();
  };

  function isSubmitEnabled(): boolean {
    return name.trim().length > 0 && propertyPath.trim().length > 0;
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={t("common.facets.addNewFacet")}
      className="w-[400px]"
    >
      <div className="mt-3 max-h-96 overflow-auto space-y-1">
        <div>
          <div className="mb-1">
            <span className="font-bold">
              {t("common.facets.facetNameOptional")}
            </span>
          </div>

          <TextInput
            placeholder={t("common.facets.enterFacetName")}
            required={true}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mb-4"
          />
        </div>
        <div>
          <div className="mb-1">
            <span className="font-bold">
              {t("common.facets.facetPropertyPath")}
            </span>
          </div>

          <TextInput
            placeholder={t("common.facets.enterFacetPropertyPath")}
            required={true}
            value={propertyPath}
            onChange={(e) => setPropertyPath(e.target.value)}
            className="mb-4"
          />
        </div>
      </div>
      <div className="flex flex-1 justify-end gap-2">
        <Button
          data-testid="cancel-facet-creation-btn"
          color="orange"
          size="xs"
          variant="secondary"
          onClick={close}
        >
          {t("common.actions.cancel")}
        </Button>
        <Button
          data-testid="create-facet-btn"
          color="orange"
          size="xs"
          variant="primary"
          type="submit"
          disabled={!isSubmitEnabled()}
          onClick={() => handleNewFacetCreation()}
        >
          {t("common.actions.create")}
        </Button>
      </div>
    </Modal>
  );
};
