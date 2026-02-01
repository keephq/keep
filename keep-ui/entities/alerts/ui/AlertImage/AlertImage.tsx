import React, { useState } from "react";

export const AlertImage = ({ imageUrl }: { imageUrl: string }) => {
  const [imageError, setImageError] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  if (imageError || !imageUrl) {
    console.log("Image error state:", imageError);
    console.log("Image URL received:", imageUrl);
    return null;
  }

  return (
    <div
      className="inline-block relative"
      onMouseEnter={(e) => {
        if (e.target === e.currentTarget.querySelector("img")) {
          setIsHovered(true);
        }
      }}
      onMouseLeave={() => setIsHovered(false)}
    >
      <div className="w-32 h-16">
        <img
          src={imageUrl}
          alt="Preview"
          className="w-full h-full object-cover cursor-pointer"
          onClick={() => window.open(imageUrl, "_blank")}
          onError={(e) => {
            console.error("Image loading error:", e);
            setImageError(true);
          }}
          sizes="160px"
        />

        {isHovered && (
          <div
            className="fixed z-50 ml-2"
            style={{
              left: "50%",
              top: "50%",
              transform: "translate(-50%, -50%)",
            }}
          >
            <div className="p-1 bg-white shadow-lg rounded">
              <img
                src={imageUrl}
                alt="Large preview"
                className="max-w-[600px] max-h-[600px] object-contain"
                onError={(e) => {
                  console.error("Preview image loading error:", e);
                  setImageError(true);
                }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
