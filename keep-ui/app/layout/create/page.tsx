// NewWidgetLayout.tsx
'use client';
import React, { useState } from "react";
import GridLayout from "./GridLayout";
import WidgetModal from "./WidgetModal";
import EditGridItemModal from "./EditGridItemModal";
import { usePresets } from "utils/hooks/usePresets";
import { Button, Card } from '@tremor/react';
import { LayoutItem, WidgetData, Threshold } from "./types";
import "./styles.css"

const NewWidgetLayout = () => {
  const { useAllPresets } = usePresets();
  const { data: presets } = useAllPresets();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [layout, setLayout] = useState<LayoutItem[]>([]);
  const [data, setData] = useState<WidgetData[]>([]);
  const [editingItem, setEditingItem] = useState<WidgetData | null>(null);

  const openModal = () => setIsModalOpen(true);
  const closeModal = () => setIsModalOpen(false);

  const openEditModal = (id: string) => {
    const itemToEdit = data.find(d => d.i === id) || null;
    setEditingItem(itemToEdit);
    setIsEditModalOpen(true);
  };

  const closeEditModal = () => setIsEditModalOpen(false);

  const handleAddWidget = (presetId: string, thresholds: Threshold[], name: string) => {
    const id = `w-${Date.now()}`;
    const newItem: LayoutItem = {
      i: id,
      x: (layout.length % 12) * 2,
      y: Math.floor(layout.length / 12) * 2,
      w: 3, // Increased width
      h: 3, // Increased height
      minW: 2,
      minH: 2,
      static: false
    };
    const newWidget: WidgetData = {
      ...newItem,
      thresholds,
      presetId,
      name  // Add widget name here
    };
    setLayout([...layout, newItem]);
    setData([...data, newWidget]);
  };

  const handleLayoutChange = (newLayout: LayoutItem[]) => {
    setLayout(newLayout);
    setData((prevData) =>
      prevData.map((item) => {
        const newItem = newLayout.find((l) => l.i === item.i);
        return newItem ? { ...item, ...newItem } : item;
      })
    );
  };

  const handleSaveEdit = (updatedItem: WidgetData) => {
    setData((prevData) =>
      prevData.map((item) => (item.i === updatedItem.i ? updatedItem : item))
    );
    closeEditModal();
  };

  return (
    <div className="flex flex-col overflow-hidden h-full">
      {layout.length === 0 ? (
        <Card
          className="w-full h-full flex items-center justify-center cursor-pointer"
          onClick={openModal}
        >
          <div className="text-center">
            <p className="text-lg font-medium">No widgets available</p>
            <p className="text-gray-500">Click to add your first widget</p>
          </div>
        </Card>
      ) : (
        <>
          <div className="flex justify-end mb-2">
            <Button onClick={openModal}>Add Widget</Button>
          </div>
          <Card className="w-full h-full">
            <GridLayout layout={layout} onLayoutChange={handleLayoutChange} data={data} onEdit={openEditModal} />
          </Card>
        </>
      )}
      <WidgetModal
        isOpen={isModalOpen}
        onClose={closeModal}
        onAddWidget={handleAddWidget}
        presets={presets}
      />
      <EditGridItemModal
        isOpen={isEditModalOpen}
        onClose={closeEditModal}
        item={editingItem}
        onSave={handleSaveEdit}
      />
    </div>
  );
};

export default NewWidgetLayout;
