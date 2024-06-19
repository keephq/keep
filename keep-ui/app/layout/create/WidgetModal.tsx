import React, { useState } from "react";
import Modal from "@/components/ui/Modal";
import { Button } from '@tremor/react';
import { Threshold } from "./types";

interface WidgetModalProps {
  isOpen: boolean;
  onClose: () => void;
  onAddWidget: (presetId: string, thresholds: Threshold[], name: string) => void;
  presets: { id: string; name: string; }[];
}

const WidgetModal: React.FC<WidgetModalProps> = ({ isOpen, onClose, onAddWidget, presets }) => {
  const [thresholds, setThresholds] = useState<Threshold[]>([
    { value: 0, color: '#00FF00' }, // Green
    { value: 20, color: '#FF0000' } // Red
  ]);
  const [selectedPreset, setSelectedPreset] = useState<string>('');
  const [widgetName, setWidgetName] = useState<string>('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onAddWidget(selectedPreset, thresholds, widgetName);
    setWidgetName('');
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Add a New Widget">
      <form onSubmit={handleSubmit}>
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700">Widget Name:</label>
          <input
            type="text"
            value={widgetName}
            onChange={(e) => setWidgetName(e.target.value)}
            className="border p-1 w-full"
            placeholder="Enter widget name"
            required
          />
        </div>
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700">Preset:</label>
          <select value={selectedPreset} onChange={(e) => setSelectedPreset(e.target.value)} className="border p-1 w-full">
            {presets?.map(preset => (
              <option key={preset.id} value={preset.id}>{preset.name}</option>
            ))}
          </select>
        </div>
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700">Thresholds:</label>
          {thresholds.map((threshold, index) => (
            <div key={index} className="flex items-center space-x-2 mb-2">
              <input
                type="number"
                value={threshold.value}
                onChange={(e) => setThresholds(thresholds.map((t, i) => i === index ? { ...t, value: parseInt(e.target.value, 10) } : t))}
                className="border p-1"
              />
              <input
                type="color"
                value={threshold.color}
                onChange={(e) => setThresholds(thresholds.map((t, i) => i === index ? { ...t, color: e.target.value } : t))}
                className="border p-1"
              />
            </div>
          ))}
        </div>
        <Button type="submit">Add Widget</Button>
      </form>
    </Modal>
  );
};

export default WidgetModal;
