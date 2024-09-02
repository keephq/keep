import React from 'react';
import { Button, Card } from "@tremor/react";
import { CircleStackIcon } from "@heroicons/react/24/outline";
import Image from 'next/image';

interface EmptyStateImageProps {
  message: string;
  documentationURL: string;
  imageURL: string;
  icon?: React.ElementType;
}

export function EmptyStateImage({
  message,
  documentationURL,
  imageURL,
  icon: Icon = CircleStackIcon,
}: EmptyStateImageProps) {
  return (
    <div className="h-full flex flex-col relative">
      <Card className="w-full flex-grow overflow-hidden">
        <div className="relative w-full h-full">
          <Image
            src={imageURL}
            alt="Empty state"
            layout="fill"
            objectFit="contain"
          />
        </div>
      </Card>

      <div className="absolute inset-0 bg-white bg-opacity-50 dark:bg-gray-800 dark:bg-opacity-50 flex items-center justify-center">
        <Card className="w-full max-w-md bg-white bg-opacity-70 dark:bg-gray-800 dark:bg-opacity-70">
          <div className="text-center">
            <Icon
              className="mx-auto h-7 w-7 text-tremor-content-subtle dark:text-dark-tremor-content-subtle"
              aria-hidden={true}
            />
            <p className="mt-4 text-tremor-default font-medium text-tremor-content-strong dark:text-dark-tremor-content-strong">
              {message}
            </p>
            <Button
              className="mt-4"
              color="orange"
              onClick={() => window.open(documentationURL, '_blank')}
            >
              View Documentation
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
