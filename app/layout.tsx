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
        {/* Google Fonts: Inter */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet" />
        
        {/* Force dark mode background immediately to avoid white flash */}
        <style dangerouslySetInnerHTML={{__html: `
          body {
            background-color: #0b1121; /* Darker slate */
            color: #e2e8f0;
            font-family: 'Inter', sans-serif;
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
                  fontFamily: {
                    sans: ['Inter', 'sans-serif'],
                  },
                  colors: {
                    background: '#0b1121',
                    surface: '#151e32',
                    surfaceHighlight: '#1e293b',
                    primary: '#fbbf24', // Amber-400
                    secondary: '#94a3b8',
                  }
                }
              }
            }
          }
        `}} />
        <script src="https://cdn.tailwindcss.com"></script>
      </head>
      <body className="bg-background text-white min-h-screen antialiased">
        {children}
      </body>
    </html>
  );
}