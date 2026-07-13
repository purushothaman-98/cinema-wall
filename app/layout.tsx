import React from 'react';
import './globals.css';

export const metadata = {
  title: 'Tamil Film Pulse',
  description: 'A cross-platform sentiment dashboard for recent Tamil films.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en"><body>{children}</body>
    </html>
  );
}
