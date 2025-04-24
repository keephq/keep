import {
  Card,
  Table,
  TableHead,
  TableRow,
  TableHeaderCell,
  TableBody,
  TableCell,
} from "@tremor/react";
import { EmptyStateCard } from "@/shared/ui/EmptyState/EmptyStateCard";
import { PhotoIcon } from "@heroicons/react/24/outline";
import { useProviderImages } from "@/entities/provider-images/model/useProviderImages";
import { useState, useEffect, useRef } from "react";
import {
  ImagePreviewTooltip,
  TooltipPosition,
} from "@/components/ui/ImagePreviewTooltip";

export function ProviderImagesList() {
  const { customImages, isLoading, getImageUrl } = useProviderImages();
  const [tooltipPosition, setTooltipPosition] = useState<TooltipPosition>(null);
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({});
  const [currentImage, setCurrentImage] = useState<string | null>(null);
  const imageContainerRef = useRef<HTMLDivElement | null>(null);

  const handleMouseEnter = (providerName: string) => {
    setCurrentImage(providerName);
    if (imageContainerRef.current) {
      const rect = imageContainerRef.current.getBoundingClientRect();
      setTooltipPosition({
        x: rect.right - 150,
        y: rect.top - 150,
      });
    }
  };

  const handleMouseLeave = () => {
    setTooltipPosition(null);
  };

  useEffect(() => {
    // Load all images
    const loadImages = async () => {
      if (!customImages) return;

      const urls: Record<string, string> = {};
      for (const image of customImages) {
        urls[image.provider_name] = await getImageUrl(image.provider_name);
      }
      if (Object.keys(urls).length > 0) {
        setImageUrls((prev) => ({ ...prev, ...urls }));
      }
    };

    loadImages();

    // Cleanup URLs on unmount
    return () => {
      Object.values(imageUrls).forEach(URL.revokeObjectURL);
    };
  }, [customImages]);

  if (isLoading) {
    return null; // Or a loading spinner
  }

  if (!customImages || customImages.length === 0) {
    return (
      <EmptyStateCard
        icon={PhotoIcon}
        title="No custom provider icons"
        description="Upload custom images for your providers to make them more recognizable"
      />
    );
  }

  return (
    <Card>
      <Table>
        <TableHead>
          <TableRow>
            <TableHeaderCell>Provider</TableHeaderCell>
            <TableHeaderCell>Image</TableHeaderCell>
            {/* <TableHeaderCell>Actions</TableHeaderCell> */}
          </TableRow>
        </TableHead>
        <TableBody>
          {customImages.map((image) => (
            <TableRow key={image.id} className="group">
              <TableCell>{image.provider_name}</TableCell>
              <TableCell>
                <div className="w-8 h-8 flex items-center justify-center">
                  {imageUrls[image.provider_name] && (
                    <div ref={imageContainerRef}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={imageUrls[image.provider_name]}
                        alt={image.provider_name}
                        className="inline-block size-5 xl:size-6 rounded-full"
                        onMouseEnter={() =>
                          handleMouseEnter(image.provider_name)
                        }
                        onMouseLeave={handleMouseLeave}
                      />
                    </div>
                  )}
                </div>
              </TableCell>
              {/* <TableCell>
                <button
                  onClick={() => onSelectProvider(image.provider_name)}
                  className="text-orange-500 hover:text-orange-700"
                >
                  Update
                </button>
              </TableCell> */}
            </TableRow>
          ))}
        </TableBody>
      </Table>
      {tooltipPosition && currentImage && (
        <ImagePreviewTooltip
          imageUrl={imageUrls[currentImage]}
          position={tooltipPosition}
        />
      )}
    </Card>
  );
}
