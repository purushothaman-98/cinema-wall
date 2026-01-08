import React from 'react';

export const metadata = {
  title: 'Cinema Wall',
  description: 'An IMDb-style aggregation wall for movie reviews analyzed by AI.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <script src="https://cdn.tailwindcss.com"></script>
        <script dangerouslySetInnerHTML={{__html: `
          tailwind.config = {
            theme: {
              extend: {
                colors: {
                  background: '#0f172a',
                  surface: '#1e293b',
                  primary: '#eab308',
                  secondary: '#64748b',
                }
              }
            }
          }
        `}} />
        <style dangerouslySetInnerHTML={{__html: `
          body {
            background-color: #0f172a;
            color: #f8fafc;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
          }
          /* Custom Scrollbar */
          ::-webkit-scrollbar {
            width: 8px;
          }
          ::-webkit-scrollbar-track {
            background: #0f172a; 
          }
          ::-webkit-scrollbar-thumb {
            background: #334155; 
            border-radius: 4px;
          }
          ::-webkit-scrollbar-thumb:hover {
            background: #475569; 
          }
        `}} />
      </head>
      <body>{children}</body>
    </html>
  );
}