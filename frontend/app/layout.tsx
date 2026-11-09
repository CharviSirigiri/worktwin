import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "WorkTwin",
  description: "AI work twins that help university group projects actually work.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,650;12..96,750;12..96,800&display=swap"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
