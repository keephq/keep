import React, { useState } from "react";
import { TextInput } from "@tremor/react";
import Modal from "@/components/ui/Modal";
import { CreateFacetDto } from "./models";
import { Button } from "@/components/ui";
import { FiSearch } from "react-icons/fi";
import { useFacetPotentialFields } from "./hooks";
import { useI18n } from "@/i18n/hooks/useI18n";

interface AddFacetModalWithSuggestions {
  entityName: string;
  isOpen: boolean;
  onClose: () => void;
  onAddFacet: (createFacet: CreateFacetDto) => void;
}

export const AddFacetModalWithSuggestions: React.FC<
  AddFacetModalWithSuggestions
> = ({ entityName, isOpen, onClose, onAddFacet }) => {
  const { t } = useI18n();
  const [name, setName] = useState("");
  const [propertyPath, setPropertyPath] = useState("");
  const [searchTerm, setSearchTerm] = useState("");

  const { data: propertyPathSuggestions } = useFacetPotentialFields(entityName);

  const handleNewFacetCreation = () => {
    onAddFacet({
      property_path: propertyPath,
      name: name || propertyPath,
    });
    close();
  };

  const close = () => {
    setName("");
    setPropertyPath("");
    onClose();
  };

  function isSubmitEnabled(): boolean {
    return propertyPath.trim().length > 0;
  }

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={t("common.facets.addNewFacet")}
      className="w-[400px]"
    >
      <div className="flex flex-col max-w-full overflow-hidden">
        <div className="flex-1 flex flex-col mt-3 max-h-96 space-y-1">
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
              placeholder={t("common.facets.enterFacetPropertyPathOrSelect")}
              required={true}
              value={propertyPath}
              onChange={(e) => setPropertyPath(e.target.value)}
              className="mb-4"
            />
          </div>
          <div className="flex flex-col flex-1 overflow-hidden">
            <div className="mb-1">
              <span className="font-bold">
                {t("common.facets.selectFacetPropertyPath")}
              </span>
            </div>
            {!propertyPathSuggestions && t("common.actions.loading")}
            {propertyPathSuggestions &&
              propertyPathSuggestions.length === 0 && (
                <div>{t("common.facets.noPropertyPathSuggestions")}</div>
              )}
            {propertyPathSuggestions?.length && (
              <>
                <TextInput
                  icon={FiSearch}
                  placeholder={t("common.facets.searchColumns")}
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="mb-4"
                />
                <div className="flex-1 min-w-0 overflow-auto space-y-1">
                  {propertyPathSuggestions
                    ?.filter(
                      (propPath) => !searchTerm || propPath.includes(searchTerm)
                    )
                    .map((propPath, index) => (
                      <button
                        key={propPath}
                        onClick={() => setPropertyPath(propPath)}
                        className={`w-full text-left px-4 py-2 rounded`}
                      >
                        {propPath}
                      </button>
                    ))}
                </div>
              </>
            )}
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
      </div>
    </Modal>
  );
};
