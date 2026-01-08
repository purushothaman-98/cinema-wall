'use client';

import { useEffect } from 'react';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Application Error:', error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center p-4 text-center bg-[#0f172a] text-white">
      <h2 className="text-2xl font-bold text-red-500 mb-4">Something went wrong!</h2>
      <p className="text-gray-400 mb-6 max-w-md">{error.message || "An unexpected error occurred."}</p>
      <button
        className="px-4 py-2 bg-[#eab308] text-black font-bold rounded hover:bg-yellow-400"
        onClick={() => reset()}
      >
        Try again
      </button>
    </div>
  );
}