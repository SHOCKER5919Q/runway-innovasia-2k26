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
  icons: { icon: "/favicon.svg" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0B1712" },
    { media: "(prefers-color-scheme: light)", color: "#F6F4EE" },
  ],
  width: "device-width",
  initialScale: 1,
};

/* Set the theme before first paint. The Drive reference is light by default;
   dark is an explicit choice, not a guess from the operating system. */
const THEME_BOOT = `
(function(){try{
  var t = localStorage.getItem('runway.theme') || 'light';
  document.documentElement.dataset.theme = t;
}catch(e){document.documentElement.dataset.theme='light';}})();
`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" data-theme="light" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
        <meta httpEquiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
        <meta httpEquiv="Pragma" content="no-cache" />
        <meta httpEquiv="Expires" content="0" />
        <meta name="runway-design" content="grove-v3-drive-reference" />
        <link rel="preload" href="/fonts/plus-jakarta-sans-latin.woff2" as="font" type="font/woff2" crossOrigin="" />
        <style>{`
          :root {
            --font-geist-sans: 'Plus Jakarta Sans';
            --font-display: 'Plus Jakarta Sans';
            --font-editorial: 'Instrument Serif';
            --font-geist-mono: 'JetBrains Mono';
          }
        `}</style>
      </head>
      <body>
        <a href="#main"
           className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[200] focus:rounded-full focus:bg-forest focus:px-4 focus:py-2 focus:text-white">
          Skip to content
        </a>
        <div id="main">{children}</div>
      </body>
    </html>
  );
}
