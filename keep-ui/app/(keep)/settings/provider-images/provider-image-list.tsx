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
import { useState, useEffect } from "react";

interface Props {
  onSelectProvider: (provider: string) => void;
}

export function ProviderImagesList({ onSelectProvider }: Props) {
  const { customImages, isLoading, getImageUrl } = useProviderImages();
  const [imageUrls, setImageUrls] = useState<Record<string, string>>({});

  useEffect(() => {
    // Load all images
    const loadImages = async () => {
      if (!customImages) return;

      const urls: Record<string, string> = {};
      for (const image of customImages) {
        // Skip if we already have the URL
        if (imageUrls[image.provider_name]) continue;

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
        title="No custom provider images"
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
            <TableHeaderCell>Actions</TableHeaderCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {customImages.map((image) => (
            <TableRow key={image.id} className="group">
              <TableCell>{image.provider_name}</TableCell>
              <TableCell>
                <div className="w-8 h-8 flex items-center justify-center">
                  {imageUrls[image.provider_name] && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={imageUrls[image.provider_name]}
                      alt={image.provider_name}
                      className="inline-block size-5 xl:size-6 rounded-full"
                    />
                  )}
                </div>
              </TableCell>
              <TableCell>
                <button
                  onClick={() => onSelectProvider(image.provider_name)}
                  className="text-orange-500 hover:text-orange-700"
                >
                  Update
                </button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
