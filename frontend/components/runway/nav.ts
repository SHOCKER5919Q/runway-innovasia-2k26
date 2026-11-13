import {
  Activity, Banknote, Boxes, Brain, Building2, Calendar, CircleDollarSign,
  FileBarChart, Gauge, Home, Landmark, LayoutGrid, LineChart, Lightbulb,
  Plug, Receipt, Settings, ShieldAlert, Sparkles, Users, Wallet, Workflow,
} from "lucide-react";

export type NavItem = {
  href: string; label: string; icon: any; group: string;
  blurb: string; badge?: "alerts" | "recs";
};

/** Navigation mirrors the reference board's sidebar, grouped so the list
 *  reads as a workflow rather than an alphabet. */
export const NAV: NavItem[] = [
  { href: "/app", label: "Home", icon: Home, group: "Today",
    blurb: "Your daily financial briefing" },
  { href: "/app/state-centre", label: "Business State Centre", icon: LayoutGrid, group: "Today",
    blurb: "Actual, predicted and simulated side by side" },
  { href: "/app/twin", label: "Digital Twin", icon: Workflow, group: "Today",
    blurb: "The living model of your business" },

  { href: "/app/forecasts", label: "Cash Runway", icon: LineChart, group: "Look ahead",
    blurb: "13-week forecast with P10–P90 bands" },
  { href: "/app/scenarios", label: "Scenario Lab", icon: Sparkles, group: "Look ahead",
    blurb: "Test a decision before you make it" },
  { href: "/app/risk", label: "Risk Centre", icon: ShieldAlert, group: "Look ahead",
    blurb: "Early warnings and stress tests", badge: "alerts" },
  { href: "/app/recommendations", label: "Recommendations", icon: Lightbulb, group: "Look ahead",
    blurb: "Ranked actions with evidence", badge: "recs" },

  { href: "/app/receivables", label: "Receivables", icon: CircleDollarSign, group: "Money",
    blurb: "Who owes you, and when they will pay" },
  { href: "/app/payables", label: "Payables", icon: Banknote, group: "Money",
    blurb: "What you owe, and the statutory deadlines" },
  { href: "/app/customers", label: "Customers", icon: Users, group: "Money",
    blurb: "Payment behaviour per buyer" },
  { href: "/app/suppliers", label: "Suppliers", icon: Boxes, group: "Money",
    blurb: "Dependency, terms and discounts" },
  { href: "/app/transactions", label: "Transactions", icon: Receipt, group: "Money",
    blurb: "The unified ledger" },

  { href: "/app/health", label: "Financial Health", icon: Gauge, group: "Standing",
    blurb: "Eight transparent dimensions" },
  { href: "/app/compliance", label: "Compliance Calendar", icon: Calendar, group: "Standing",
    blurb: "GST, payroll, MSMED and EMIs" },
  { href: "/app/reports", label: "Reports", icon: FileBarChart, group: "Standing",
    blurb: "Cash Health Passport and exports" },

  { href: "/app/copilot", label: "AI Copilot", icon: Brain, group: "Assist",
    blurb: "Talk to your business" },
  { href: "/app/onboarding", label: "Setup Data", icon: Boxes, group: "Assist",
    blurb: "Enter cash, invoices, bills and monthly commitments" },
  { href: "/app/integrations", label: "Integrations", icon: Plug, group: "Assist",
    blurb: "Imports and connector status" },
  { href: "/app/settings", label: "Settings", icon: Settings, group: "Assist",
    blurb: "Policies, people and data" },
];

export const ACCOUNTANT_NAV: NavItem = {
  href: "/app/accountant", label: "Client Portfolio", icon: Building2, group: "Assist",
  blurb: "Every business you have access to",
};

export const GROUPS = ["Today", "Look ahead", "Money", "Standing", "Assist"];
