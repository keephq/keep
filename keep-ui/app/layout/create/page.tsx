'use client';
import React, { useState } from "react";
import GridLayout from "./GridLayout";
import WidgetModal from "./WidgetModal";
import { usePresets } from "utils/hooks/usePresets";
import { Button, Card } from '@tremor/react';
import { LayoutItem, WidgetData, Threshold } from "./types";
import { Preset } from "app/alerts/models";
import "./styles.css";

const NewWidgetLayout: React.FC = () => {
  const { useAllPresets, useStaticPresets } = usePresets();
  const { data: presets = [] } = useAllPresets();
  const { data: staticPresets = [] } = useStaticPresets();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [layout, setLayout] = useState<LayoutItem[]>([]);
  const [data, setData] = useState<WidgetData[]>([]);
  const [editingItem, setEditingItem] = useState<WidgetData | null>(null);

  const allPresets = [...presets, ...staticPresets];
  const openModal = () => {
    setEditingItem(null); // Ensure new modal opens without editing item context
    setIsModalOpen(true);
  };
  const closeModal = () => setIsModalOpen(false);

  const handleAddWidget = (preset: Preset, thresholds: Threshold[], name: string) => {
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
      preset,
      name,
    };
    setLayout((prevLayout) => [...prevLayout, newItem]);
    setData((prevData) => [...prevData, newWidget]);
  };

  const handleEditWidget = (id: string) => {
    const itemToEdit = data.find(d => d.i === id) || null;
    setEditingItem(itemToEdit);
    setIsModalOpen(true);
  };

  const handleSaveEdit = (updatedItem: WidgetData) => {
    setData((prevData) =>
      prevData.map((item) => (item.i === updatedItem.i ? updatedItem : item))
    );
    closeModal();
  };

  const handleDeleteWidget = (id: string) => {
    setLayout(layout.filter(item => item.i !== id));
    setData(data.filter(item => item.i !== id));
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
            <Button color="orange" onClick={openModal}>Add Widget</Button>
          </div>
          <Card className="w-full h-full">
            <GridLayout
              layout={layout}
              onLayoutChange={handleLayoutChange}
              data={data}
              onEdit={handleEditWidget}
              onDelete={handleDeleteWidget}
            />
          </Card>
        </>
      )}
      <WidgetModal
        isOpen={isModalOpen}
        onClose={closeModal}
        onAddWidget={handleAddWidget}
        onEditWidget={handleSaveEdit}
        presets={allPresets}
        editingItem={editingItem}
      />
    </div>
  );
};

export default NewWidgetLayout;
