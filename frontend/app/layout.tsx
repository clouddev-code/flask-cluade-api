import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'AI Chat Assistant',
  description: 'Streaming対応のNext.jsチャットアプリ',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body className="antialiased bg-gray-50 dark:bg-gray-900">
        {children}
      </body>
    </html>
  );
}
