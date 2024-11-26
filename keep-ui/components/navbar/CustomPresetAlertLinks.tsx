import { CSSProperties, useEffect, useState } from "react";
import { Session } from "next-auth";
import { toast } from "react-toastify";
import { usePresets } from "utils/hooks/usePresets";
import { AiOutlineSwap } from "react-icons/ai";
import { usePathname, useRouter } from "next/navigation";
import { Subtitle } from "@tremor/react";
import { LinkWithIcon } from "../LinkWithIcon";
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
import { Preset } from "@/app/(keep)/alerts/models";
import { AiOutlineSound } from "react-icons/ai";
// Using dynamic import to avoid hydration issues with react-player
import dynamic from "next/dynamic";
const ReactPlayer = dynamic(() => import("react-player"), { ssr: false });
// import css
import "./CustomPresetAlertLink.css";
import clsx from "clsx";
import { useApi } from "@/shared/lib/hooks/useApi";

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

  const getIcon = () => {
    if (preset.should_do_noise_now) {
      return AiOutlineSound;
    } else if (preset.is_noisy) {
      return AiOutlineSound;
    } else {
      return AiOutlineSwap;
    }
  };

  return (
    <li key={preset.id} ref={setNodeRef} style={dragStyle} {...listeners}>
      <LinkWithIcon
        href={href}
        icon={getIcon()}
        count={preset.alerts_count}
        isDeletable={true}
        onDelete={() => deletePreset(preset.id, preset.name)}
        isExact={true}
        className={clsx(
          "flex items-center space-x-2 text-sm p-1 text-slate-400 font-medium rounded-lg",
          {
            "bg-stone-200/50": isActive,
            "hover:text-orange-400 focus:ring focus:ring-orange-300 group hover:bg-stone-200/50":
              !isDragging,
          }
        )}
      >
        <Subtitle
          className={clsx("truncate max-w-[7.5rem]", {
            "text-orange-400": isActive,
          })}
          title={preset.name}
        >
          {preset.name.charAt(0).toUpperCase() + preset.name.slice(1)}
        </Subtitle>
      </LinkWithIcon>
    </li>
  );
};
type CustomPresetAlertLinksProps = {
  session: Session;
  selectedTags: string[];
};

export const CustomPresetAlertLinks = ({
  session,
  selectedTags,
}: CustomPresetAlertLinksProps) => {
  const api = useApi();

  const { useAllPresets, presetsOrderFromLS, setPresetsOrderFromLS } =
    usePresets();
  const { data: presets = [], mutate: presetsMutator } = useAllPresets({
    revalidateIfStale: false,
    revalidateOnFocus: false,
  });

  const pathname = usePathname();
  const router = useRouter();
  const [presetsOrder, setPresetsOrder] = useState<Preset[]>([]);

  // Check for noisy presets and control sound playback
  const anyNoisyNow = presets.some((preset) => preset.should_do_noise_now);

  const checkValidPreset = (preset: Preset) => {
    if (!preset.is_private) {
      return true;
    }
    return preset && preset.created_by == session?.user?.email;
  };

  useEffect(() => {
    const filteredLS = presetsOrderFromLS.filter(
      (preset) =>
        ![
          "feed",
          "deleted",
          "dismissed",
          "without-incident",
          "groups",
        ].includes(preset.name)
    );

    // Combine live presets and local storage order
    const combinedOrder = presets.reduce<Preset[]>(
      (acc, preset: Preset) => {
        if (!acc.find((p) => p.id === preset.id)) {
          acc.push(preset);
        }
        return acc.filter((preset) => checkValidPreset(preset));
      },
      [...filteredLS]
    );

    // Only update state if there's an actual change to prevent infinite loops
    if (JSON.stringify(presetsOrder) !== JSON.stringify(combinedOrder)) {
      setPresetsOrder(combinedOrder);
    }
  }, [presets, presetsOrderFromLS]);
  // Filter presets based on tags, or return all if no tags are selected
  const filteredOrderedPresets =
    selectedTags.length === 0
      ? presetsOrder
      : presetsOrder.filter((preset) =>
          preset.tags.some((tag) => selectedTags.includes(tag.name))
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
      try {
        await api.delete(`/preset/${presetId}`);

        toast(`Preset ${presetName} deleted!`, {
          position: "top-left",
          type: "success",
        });

        await presetsMutator();

        // remove preset from saved order
        setPresetsOrderFromLS((oldOrder) =>
          oldOrder.filter((p) => p.id !== presetId)
        );

        router.push("/alerts/feed"); // Redirect to feed
      } catch (error) {
        toast(`Error deleting preset ${presetName}: ${error}`, {
          position: "top-left",
          type: "error",
        });
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
        {filteredOrderedPresets.map((preset) => (
          <PresetAlert
            key={preset.id}
            preset={preset}
            pathname={pathname}
            deletePreset={deletePreset}
          />
        ))}
      </SortableContext>
      {/* React Player for playing alert sound */}
      <ReactPlayer
        // TODO: cache the audio file fiercely
        url="/music/alert.mp3"
        playing={anyNoisyNow}
        volume={0.5}
        loop={true}
        width="0"
        height="0"
        playsinline
        className="absolute -z-10"
      />
    </DndContext>
  );
};
