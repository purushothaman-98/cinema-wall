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
        <meta charSet="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        {/* Force dark mode background immediately to avoid white flash */}
        <style dangerouslySetInnerHTML={{__html: `
          body {
            background-color: #0f172a;
            color: #f8fafc;
            font-family: sans-serif;
            margin: 0;
            min-height: 100vh;
          }
        `}} />
        {/* Load Tailwind Config BEFORE the library */}
        <script dangerouslySetInnerHTML={{__html: `
          window.tailwind = {
            config: {
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
          }
        `}} />
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body className="bg-background text-white min-h-screen">
        {children}
      </body>
    </html>
  );
}