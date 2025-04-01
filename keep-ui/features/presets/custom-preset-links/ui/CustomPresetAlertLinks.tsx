import { CSSProperties, useCallback } from "react";
import { usePresets } from "@/entities/presets/model/usePresets";
import { AiOutlineSwap } from "react-icons/ai";
import { usePathname, useRouter } from "next/navigation";
import { Icon, Subtitle } from "@tremor/react";
import { LinkWithIcon } from "@/components/LinkWithIcon";
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
import { AiOutlineSound } from "react-icons/ai";
// Using dynamic import to avoid hydration issues with react-player
import dynamic from "next/dynamic";
const ReactPlayer = dynamic(() => import("react-player"), { ssr: false });
// import css
import "./CustomPresetAlertLink.css";
import clsx from "clsx";
import { Preset } from "@/entities/presets/model/types";
import { usePresetActions } from "@/entities/presets/model/usePresetActions";
import { usePresetPolling } from "@/entities/presets/model/usePresetPolling";
import { usePresetAlertsCount } from "../model/usePresetAlertsCount";
import { FireIcon } from "@heroicons/react/24/outline";

type AlertPresetLinkProps = {
  preset: Preset;
  pathname: string | null;
  isDeletable?: boolean;
  deletePreset?: (id: string, name: string) => void;
};

export const AlertPresetLink = ({
  preset,
  pathname,
  deletePreset,
  isDeletable = false,
}: AlertPresetLinkProps) => {
  const href = `/alerts/${preset.name.toLowerCase()}`;
  const isActive = decodeURIComponent(pathname?.toLowerCase() || "") === href;

  const { totalCount } = usePresetAlertsCount(
    preset.options.find((option) => option.label === "CEL")?.value || "",
    preset.counter_shows_firing_only
  );

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

  const renderBeforeCount = useCallback(() => {
    if (preset.counter_shows_firing_only) {
      return (
        <Icon
          className="p-0 relative top-[1px]"
          size={"xs"}
          icon={FireIcon}
        ></Icon>
      );
    }
  }, [preset]);

  return (
    <li key={preset.id} ref={setNodeRef} style={dragStyle} {...listeners}>
      <LinkWithIcon
        href={href}
        icon={getIcon()}
        count={totalCount}
        isDeletable={isDeletable}
        onDelete={() => deletePreset && deletePreset(preset.id, preset.name)}
        isExact={true}
        renderBeforeCount={renderBeforeCount}
        className={clsx(
          "flex items-center space-x-2 p-1 text-slate-400 font-medium rounded-lg",
          {
            "bg-stone-200/50": isActive,
            "hover:text-orange-400 focus:ring focus:ring-orange-300 group hover:bg-stone-200/50":
              !isDragging,
          }
        )}
      >
        <Subtitle
          className={clsx("truncate text-xs max-w-24", {
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
  selectedTags: string[];
};

export const CustomPresetAlertLinks = ({
  selectedTags,
}: CustomPresetAlertLinksProps) => {
  const { deletePreset } = usePresetActions();

  const { dynamicPresets: presets, setLocalDynamicPresets } = usePresets({
    revalidateIfStale: false,
    revalidateOnFocus: false,
  });

  usePresetPolling();

  const pathname = usePathname();
  const router = useRouter();

  // Check for noisy presets and control sound playback
  const anyNoisyNow = presets?.some((preset) => preset.should_do_noise_now);

  // Filter presets based on tags, or return all if no tags are selected
  const filteredOrderedPresets =
    selectedTags.length === 0
      ? presets
      : presets.filter((preset) =>
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

  const deletePresetAndRedirect = (presetId: string, presetName: string) => {
    deletePreset(presetId, presetName).then(() => {
      router.push("/alerts/feed");
    });
  };

  const onDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over === null) {
      return;
    }

    const fromIndex = presets.findIndex(
      ({ id }) => id === active.id.toString()
    );
    const toIndex = presets.findIndex(({ id }) => id === over.id.toString());

    if (toIndex === -1) {
      return;
    }

    const reorderedCols = [...presets];
    const reorderedItem = reorderedCols.splice(fromIndex, 1);
    reorderedCols.splice(toIndex, 0, reorderedItem[0]);

    setLocalDynamicPresets(reorderedCols);
  };

  return (
    <DndContext
      key="preset-alerts"
      sensors={sensors}
      collisionDetection={rectIntersection}
      onDragEnd={onDragEnd}
    >
      <SortableContext key="preset-alerts" items={presets}>
        {filteredOrderedPresets.map((preset) => (
          <AlertPresetLink
            key={preset.id}
            preset={preset}
            pathname={pathname}
            isDeletable={true}
            deletePreset={deletePresetAndRedirect}
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
