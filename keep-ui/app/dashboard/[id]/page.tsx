'use client';
import React, { useState, ChangeEvent } from "react";
import GridLayout from "../GridLayout";
import WidgetModal from "../WidgetModal";
import { usePresets } from "utils/hooks/usePresets";
import { Button, Card, TextInput, Subtitle, Icon } from '@tremor/react';
import { LayoutItem, WidgetData, Threshold } from "../types";
import { Preset } from "app/alerts/models";
import { FiSave, FiEdit2 } from "react-icons/fi";
import { getApiURL } from "utils/apiUrl";
import { useSession } from "next-auth/react";
import "./../styles.css";

const NewWidgetLayout: React.FC = () => {
  const { useAllPresets, useStaticPresets } = usePresets();
  const { data: presets = [] } = useAllPresets();
  const { data: staticPresets = [] } = useStaticPresets();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [layout, setLayout] = useState<LayoutItem[]>([]);
  const [widgetData, setWidgetData] = useState<WidgetData[]>([]);
  const [editingItem, setEditingItem] = useState<WidgetData | null>(null);
  const [dashboardName, setDashboardName] = useState("My Dashboard");
  const [isEditingName, setIsEditingName] = useState(false);
  const { data: session } = useSession();

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
      w: 3,
      h: 3,
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
    setWidgetData((prevData) => [...prevData, newWidget]);
  };

  const handleEditWidget = (id: string) => {
    const itemToEdit = widgetData.find(d => d.i === id) || null;
    setEditingItem(itemToEdit);
    setIsModalOpen(true);
  };

  const handleSaveEdit = (updatedItem: WidgetData) => {
    setWidgetData((prevData) =>
      prevData.map((item) => (item.i === updatedItem.i ? updatedItem : item))
    );
    closeModal();
  };

  const handleDeleteWidget = (id: string) => {
    setLayout(layout.filter(item => item.i !== id));
    setWidgetData(widgetData.filter(item => item.i !== id));
  };

  const handleLayoutChange = (newLayout: LayoutItem[]) => {
    setLayout(newLayout);
    setWidgetData((prevData) =>
      prevData.map((item) => {
        const newItem = newLayout.find((l) => l.i === item.i);
        return newItem ? { ...item, ...newItem } : item;
      })
    );
  };

  const handleSaveDashboard = async () => {
    try {
      const apiUrl = getApiURL();
      const response = await fetch(`${apiUrl}/dashboard`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session!.accessToken}`,
        },
        body: JSON.stringify({
          dashboard_name: dashboardName,
          dashboard_config:{
            layout: layout,
            widget_data: widgetData,
          }
        }),
      });

      if (!response.ok) {
        throw new Error(`Failed to save dashboard: ${response.statusText}`);
      }

      const result = await response.json();
      console.log("Dashboard saved successfully", result);
    } catch (error) {
      console.error("Error saving dashboard", error);
    }
  };

  const toggleEditingName = () => {
    setIsEditingName(!isEditingName);
  };

  const handleNameChange = (e: ChangeEvent<HTMLInputElement>) => {
    setDashboardName(e.target.value);
  };

  return (
    <div className="flex flex-col overflow-hidden h-full p-4">
      <div className="flex items-center justify-between mb-4">
      <div className="relative">
          {isEditingName ? (
            <TextInput
              value={dashboardName}
              onChange={handleNameChange}
              onBlur={toggleEditingName}
              placeholder="Dashboard Name"
              className="border-orange-500 focus:border-orange-600 focus:ring-orange-600"
            />
          ) : (
            <Subtitle color="orange" className="mr-2">{dashboardName}</Subtitle>
          )}
          <Icon
            size="xs"
            icon={FiEdit2}
            onClick={toggleEditingName}
            className="cursor-pointer absolute right-0 top-0 transform -translate-y-1/2 translate-x-1/2 text-sm"
            color="orange"
          />
        </div>
        <div className="flex">
          <Button
            icon={FiSave}
            color="orange"
            size="sm"
            onClick={handleSaveDashboard}
            tooltip="Save current dashboard"
          />
          <Button color="orange" onClick={openModal} className="ml-2">Add Widget</Button>
        </div>
      </div>
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
        <Card className="w-full h-full">
          <GridLayout
            layout={layout}
            onLayoutChange={handleLayoutChange}
            data={widgetData}
            onEdit={handleEditWidget}
            onDelete={handleDeleteWidget}
          />
        </Card>
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
