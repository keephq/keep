import React, { useState, useEffect } from "react";
import Modal from "@/components/ui/Modal";
import { Button } from "@tremor/react";
import { WidgetData, Threshold } from "./types";

interface EditGridItemModalProps {
  isOpen: boolean;
  onClose: () => void;
  item: WidgetData | null;
  onSave: (updatedItem: WidgetData) => void;
}

const EditGridItemModal: React.FC<EditGridItemModalProps> = ({
  isOpen,
  onClose,
  item,
  onSave,
}) => {
  const [thresholds, setThresholds] = useState<Threshold[]>([]);

  useEffect(() => {
    if (item?.thresholds) {
      setThresholds(item.thresholds);
    }
  }, [item]);

  const handleSave = () => {
    if (item) {
      onSave({ ...item, thresholds });
    }
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Edit Widget">
      {item && (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSave();
          }}
        >
          <div>
            <label>Thresholds:</label>
            {thresholds.map((threshold, index) => (
              <div key={index} className="flex items-center space-x-2">
                <input
                  type="number"
                  value={threshold.value}
                  onChange={(e) =>
                    setThresholds(
                      thresholds.map((t, i) =>
                        i === index
                          ? { ...t, value: parseInt(e.target.value, 10) }
                          : t
                      )
                    )
                  }
                  className="border p-1"
                />
                <input
                  type="color"
                  value={threshold.color}
                  onChange={(e) =>
                    setThresholds(
                      thresholds.map((t, i) =>
                        i === index ? { ...t, color: e.target.value } : t
                      )
                    )
                  }
                  className="border p-1"
                />
              </div>
            ))}
          </div>
          <Button type="submit">Save</Button>
        </form>
      )}
    </Modal>
  );
};

export default EditGridItemModal;
