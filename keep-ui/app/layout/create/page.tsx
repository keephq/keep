'use client';
import React, { useState } from 'react';
import { Responsive, WidthProvider } from 'react-grid-layout';
import 'react-grid-layout/css/styles.css';
import { Button } from '@tremor/react';
import Modal from "@/components/ui/Modal";
import { usePresets } from "utils/hooks/usePresets";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import { ChartData, ChartOptions } from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const ResponsiveGridLayout = WidthProvider(Responsive);

interface Threshold {
  value: number;
  color: string;
}

interface Widget {
  id: string;
  name: string;
  thresholds: Threshold[];
}

interface LayoutItem {
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  static: boolean;
}

const NewGridLayout = () => {
  const { useAllPresets } = usePresets();
  const { data: presets } = useAllPresets(); // Assuming this returns the actual presets
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [newWidget, setNewWidget] = useState<Widget>({ id: '', name: '', thresholds: [] });
  const [layout, setLayout] = useState<LayoutItem[]>([]);
  const [thresholds, setThresholds] = useState<Threshold[]>([]);

  const onLayoutChange = (newLayout) => {
    setLayout(newLayout);
  };

  const openModal = () => setIsModalOpen(true);
  const closeModal = () => {
    setIsModalOpen(false);
    setNewWidget({ id: '', name: '', thresholds: [] });
    setThresholds([]);
  };

  const handleAddThreshold = () => {
    setThresholds([...thresholds, { value: 0, color: '#ff0000' }]);
  };

  const handleThresholdChange = (index, field, value) => {
    const updatedThresholds = thresholds.map((threshold, i) => (
      i === index ? { ...threshold, [field]: value } : threshold
    ));
    setThresholds(updatedThresholds);
  };

  const handleAddWidget = () => {
    const id = `w-${Date.now()}`;
    setLayout([...layout, {
      i: id,
      x: (layout.length * 4) % (12 - 4),
      y: Infinity,
      w: 4,
      h: 2,
      static: false
    }]);
    closeModal();
  };

  // Sample data for the chart
  const data: ChartData<'line'> = {
    labels: ['January', 'February', 'March', 'April', 'May', 'June', 'July'],
    datasets: [
      {
        label: 'Sample Data',
        fill: false,
        lineTension: 0.1,
        backgroundColor: 'rgba(75,192,192,0.4)',
        borderColor: 'rgba(75,192,192,1)',
        borderCapStyle: 'butt' as 'butt',
        borderDash: [] as number[],
        borderDashOffset: 0.0,
        borderJoinStyle: 'miter' as 'miter',
        pointBorderColor: 'rgba(75,192,192,1)',
        pointBackgroundColor: '#fff',
        pointBorderWidth: 1,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: 'rgba(75,192,192,1)',
        pointHoverBorderColor: 'rgba(220,220,220,1)',
        pointHoverBorderWidth: 2,
        pointRadius: 1,
        pointHitRadius: 10,
        data: [65, 59, 80, 81, 56, 55, 40] as number[]
      }
    ]
  };

  return (
    <div style={{ marginTop: '20px' }}>
      <h1>Create New Grid Layout</h1>
      <Button onClick={openModal}>Add Widget</Button>
      <ResponsiveGridLayout className="layout" layouts={{ lg: layout }}
                            onLayoutChange={onLayoutChange}
                            breakpoints={{ lg: 1200, md: 996, sm: 768, xs: 480, xxs: 0 }}
                            cols={{ lg: 12, md: 10, sm: 6, xs: 4, xxs: 2 }}
                            rowHeight={30}>
        {layout.map(item => (
          <div key={item.i} className="grid-item" data-grid={item}>
            <Line data={data} />
          </div>
        ))}
      </ResponsiveGridLayout>
      <Modal
        isOpen={isModalOpen}
        onClose={closeModal}
        title="Add a New Widget">
        <form onSubmit={(e) => {
          e.preventDefault();
          setNewWidget({ ...newWidget, thresholds });
          handleAddWidget();
        }}>
          <label>
            Preset:
            <select onChange={(e) => setNewWidget({ ...newWidget, id: e.target.value, name: presets?.find(p => p.id === e.target.value)?.name || '' })}>
              {presets?.map(preset => (
                <option key={preset.id} value={preset.id}>{preset.name}</option>
              ))}
            </select>
          </label>
          <div>
            <Button type="button" onClick={handleAddThreshold}>Add Another Threshold</Button>
            {thresholds.map((threshold, index) => (
              <div key={index}>
                <label>
                  Threshold {index + 1} Value:
                  <input type="number" value={threshold.value} onChange={(e) => handleThresholdChange(index, 'value', parseInt(e.target.value, 10))} />
                </label>
                <label>
                  Color:
                  <input type="color" value={threshold.color} onChange={(e) => handleThresholdChange(index, 'color', e.target.value)} />
                </label>
              </div>
            ))}
          </div>
          <Button type="submit">Add Widget</Button>
        </form>
      </Modal>
    </div>
  );
};

export default NewGridLayout;
