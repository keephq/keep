"use client"

import { AnimatePresence, motion } from "framer-motion";
import { ReactElement, useState } from "react";

export const HoverEffect = ({
    idx, children
}: {
    children: ReactElement,
    idx: number
}) => {
    let [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

    return (
        <div
            className="relative group  block p-1.5"
            onMouseEnter={() => setHoveredIndex(idx)}
            onMouseLeave={() => setHoveredIndex(null)}
        >
            <AnimatePresence>
                {hoveredIndex === idx && (
                    <motion.span
                        className="absolute inset-0 h-full w-full bg-orange-100 border border-orange-300 block  rounded-lg"
                        layoutId="hoverBackground"
                        initial={{ opacity: 0 }}
                        animate={{
                            opacity: 1,
                            transition: { duration: 0.15 },
                        }}
                        exit={{
                            opacity: 0,
                            transition: { duration: 0.15, delay: 0.2 },
                        }}
                    />
                )}
            </AnimatePresence>
            {children}
        </div>
    );
};
