import "../styles/globals.css";
import { VideoGenSidebar } from "@/components/VideoGenSidebar";

export const metadata = {
  title: "Video Gen UI",
  description: "Dev UI",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <div className="flex min-h-screen">
          <VideoGenSidebar />
          <div className="flex-1 p-6 ml-64 md:ml-0">
            {children}
          </div>
        </div>
      </body>
    </html>
  );
}

