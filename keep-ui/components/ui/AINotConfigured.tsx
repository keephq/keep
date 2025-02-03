import React from 'react';

interface AINotConfiguredProps {
  featureName: string;
}

const AINotConfigured: React.FC<AINotConfiguredProps> = ({ featureName }) => {
  return (
    <div className="p-4 bg-gray-50 rounded-lg border border-gray-200">
      <p className="text-gray-700 text-center">
        To enable {featureName}, please run Keep with LLM provider. <br/> Check{' '}
        <a
          href="https://keep.docs.fauf.dev/features/llm-support"
          className="text-orange-600 hover:underline"
          target="_blank"
          rel="noopener noreferrer"
        >
          documentation
        </a>{' '}
        for deployment details.
      </p>
    </div>
  );
};

export default AINotConfigured;