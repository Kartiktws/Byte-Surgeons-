import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Logo } from "@/app/components";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Byte Surgeons",
  description: "Compress and decompress DICOM and STL files",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} min-h-screen antialiased`}
      >
        <div className="page-bg relative flex min-h-screen flex-col">
          <header className="flex px-4 pt-6 flex-start flex-start gap-2">
            <Logo className="h-10 w-10" />
            <h1 className="text-2xl font-bold tracking-tight text-slate-800 dark:text-slate-100">
              Byte Surgeons
            </h1>
          </header>
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
