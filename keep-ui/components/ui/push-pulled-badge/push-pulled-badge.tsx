export default function PushPullBadge({ pushed }: { pushed: boolean }) {
  return pushed ? (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-white border border-gray-200">
      <svg
        className=" ml-1 h-3.5 w-3.5 text-gray-500 mr-1"
        fill="none"
        height="24"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        viewBox="0 0 24 24"
        width="24"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path d="M5 12h14" />
        <path d="m12 5 7 7-7 7" />
      </svg>
      Pushed
    </span>
  ) : (
    <span className="inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-medium bg-white border border-gray-200">
      <svg
        className=" ml-1 h-3.5 w-3.5 text-gray-500 mr-1"
        fill="none"
        height="24"
        stroke="currentColor"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
        viewBox="0 0 24 24"
        width="24"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path d="m12 19-7-7 7-7" />
        <path d="M19 12H5" />
      </svg>
      Pulled
    </span>
  );
}
