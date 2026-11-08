import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "RUNWAY — Financial Intelligence OS for Indian MSMEs",
    template: "%s · RUNWAY",
  },
  description:
    "RUNWAY turns an MSME's transactions into understanding, foresight and better "
    + "decisions: a reconciled ledger, a 13-week probabilistic cash forecast, and a "
    + "scenario lab for testing a decision before making it.",
  applicationName: "RUNWAY",
  keywords: ["MSME", "cash flow forecasting", "India", "GST", "working capital",
             "financial intelligence", "digital twin"],
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#06100B" },
    { media: "(prefers-color-scheme: light)", color: "#fbfbfe" },
  ],
  width: "device-width",
  initialScale: 1,
};

/* Set the theme before first paint so a light-mode user never sees a dark flash. */
const THEME_BOOT = `
(function(){try{
  var t = localStorage.getItem('runway.theme') || 'dark';
  document.documentElement.dataset.theme = t;
}catch(e){document.documentElement.dataset.theme='dark';}})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Sora:wght@500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        <style>{`
          :root {
            --font-geist-sans: 'Inter';
            --font-display: 'Sora';
            --font-geist-mono: 'JetBrains Mono';
          }
        `}</style>
      </head>
      <body>
        <a href="#main"
           className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[200] focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground">
          Skip to content
        </a>
        <div id="main">{children}</div>
      </body>
    </html>
  );
}
