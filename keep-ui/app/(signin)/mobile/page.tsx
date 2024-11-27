export default function MobileLanding() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6 text-center">
      <div className="max-w-md space-y-6">
        {/* Logo/Icon Section */}
        <div className="text-5xl mb-8">📱</div>

        {/* Main Message */}
        <h1 className="text-2xl font-bold text-gray-900 mb-4">
          Mobile Support Coming Soon!
        </h1>

        {/* Description */}
        <p className="text-gray-600 mb-8">
          We're not supporting mobile devices yet, but we're working on it!
        </p>

        {/* GitHub Button */}
        <a
          href="https://github.com/your-repo-here"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center justify-center gap-2 bg-black hover:bg-gray-800 text-white font-medium py-3 px-6 rounded-lg transition-colors"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
          </svg>
          Star us on GitHub
        </a>

        {/* Desktop Alternative */}
        <p className="text-sm text-gray-500 mt-8">
          Want to try it now? Visit us on your desktop browser!
        </p>
      </div>
    </div>
  );
}
