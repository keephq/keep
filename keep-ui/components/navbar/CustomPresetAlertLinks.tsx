import { CSSProperties } from "react";
import { Session } from "next-auth";
import { toast } from "react-toastify";
import { Trashcan } from "components/icons";
import { getApiURL } from "utils/apiUrl";
import { usePresets } from "utils/hooks/usePresets";
import { AiOutlineSwap } from "react-icons/ai";
import { usePathname, useRouter } from "next/navigation";
import { Icon } from "@tremor/react";
import classNames from "classnames";
import Link from "next/link";
import {
  DndContext,
  DragEndEvent,
  PointerSensor,
  TouchSensor,
  rectIntersection,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import { SortableContext, useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Preset } from "app/alerts/models";
import { useLocalStorage } from "utils/hooks/useLocalStorage";

type PresetAlertProps = {
  preset: Preset;
  pathname: string | null;
  deletePreset: (id: string, name: string) => void;
};

const PresetAlert = ({ preset, pathname, deletePreset }: PresetAlertProps) => {
  const href = `/alerts/${preset.name.toLowerCase()}`;
  const isActive = decodeURIComponent(pathname?.toLowerCase() || "") === href;

  const { listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({
      id: preset.id,
    });

  const dragStyle: CSSProperties = {
    opacity: isDragging ? 0.5 : 1,
    transform: CSS.Translate.toString(transform),
    transition,
    cursor: isDragging ? "grabbing" : "grab",
  };

  return (
    <li key={preset.id} ref={setNodeRef} style={dragStyle} {...listeners}>
      <span
        className={classNames(
          "flex items-center space-x-2 text-sm p-1 text-slate-400 font-medium rounded-lg",
          {
            "bg-stone-200/50": isActive,
            "hover:text-orange-400 focus:ring focus:ring-orange-300 group hover:bg-stone-200/50":
              !isDragging,
          }
        )}
      >
        <Link
          className={classNames("flex items-center flex-1", {
            "pointer-events-none cursor-auto": isDragging,
          })}
          tabIndex={0}
          href={href}
        >
          <Icon
            className={classNames("group-hover:text-orange-400", {
              "text-orange-400": isActive,
              "text-slate-400": !isActive,
            })}
            icon={AiOutlineSwap}
          />
          <span
            className={classNames("truncate max-w-[7.5rem]", {
              "text-orange-400": isActive,
            })}
            title={preset.name}
          >
            {preset.name}
          </span>
        </Link>
        <button onClick={() => deletePreset(preset.id, preset.name)}>
          <Icon className="text-slate-400 hover:text-red-500" icon={Trashcan} />
        </button>
      </span>
    </li>
  );
};

type CustomPresetAlertLinksProps = {
  session: Session;
};

export const CustomPresetAlertLinks = ({
  session,
}: CustomPresetAlertLinksProps) => {
  const apiUrl = getApiURL();

  const { useAllPresets } = usePresets();
  const { data: presets = [], mutate: presetsMutator } = useAllPresets({
    revalidateIfStale: false,
  });

  const pathname = usePathname();
  const router = useRouter();

  const [presetsOrderFromLS, setPresetsOrderFromLS] = useLocalStorage<Preset[]>(
    "presets-order",
    []
  );

  const presetsOrder = presets.reduce<Preset[]>(
    (acc, preset) =>
      acc.find((p) => p.id === preset.id) ? acc : acc.concat(preset),
    presetsOrderFromLS
  );

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        tolerance: 50,
        distance: 10,
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        tolerance: 50,
        distance: 10,
      },
    })
  );

  const deletePreset = async (presetId: string, presetName: string) => {
    const isDeleteConfirmed = confirm(
      `You are about to delete preset ${presetName}. Are you sure?`
    );

    if (isDeleteConfirmed) {
      const response = await fetch(`${apiUrl}/preset/${presetId}`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${session.accessToken}`,
        },
      });

      if (response.ok) {
        toast(`Preset ${presetName} deleted!`, {
          position: "top-left",
          type: "success",
        });

        await presetsMutator();

        // remove preset from saved order
        setPresetsOrderFromLS((oldOrder) =>
          oldOrder.filter((p) => p.id !== presetId)
        );

        router.push("/alerts/feed");
      }
    }
  };

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over === null) {
      return;
    }

    const fromIndex = presetsOrder.findIndex(
      ({ id }) => id === active.id.toString()
    );
    const toIndex = presetsOrder.findIndex(
      ({ id }) => id === over.id.toString()
    );

    if (toIndex === -1) {
      return;
    }

    const reorderedCols = [...presetsOrder];
    const reorderedItem = reorderedCols.splice(fromIndex, 1);
    reorderedCols.splice(toIndex, 0, reorderedItem[0]);

    setPresetsOrderFromLS(reorderedCols);
  };

  return (
    <DndContext
      key="preset-alerts"
      sensors={sensors}
      collisionDetection={rectIntersection}
      onDragEnd={onDragEnd}
    >
      <SortableContext key="preset-alerts" items={presetsOrder}>
        {presetsOrder.map((preset) => (
          <PresetAlert
            key={preset.id}
            preset={preset}
            pathname={pathname}
            deletePreset={deletePreset}
          />
        ))}
      </SortableContext>
    </DndContext>
  );
};
