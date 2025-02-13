import React from 'react';
import { Navigation } from 'lucide-react';
import { useRouter } from "next/navigation";

interface PresetLinkButtonProps {
    routePath: string;
}

const PresetLinkButton: React.FC<PresetLinkButtonProps> = ({
    routePath
}) => {
    const router = useRouter();

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
        e.stopPropagation();
        router.push(routePath);
    };

    return (
        <div className="w-44 text-right">
            <div className="relative inline-block text-left z-10">
                <div>
                    <button
                        onClick={handleClick}
                        className="inline-flex justify-center items-center hover:bg-gray-100 w-8 h-8"
                    >
                        <Navigation color='gray' />
                    </button>
                </div>
            </div>
        </div>
    );
};

export default PresetLinkButton;