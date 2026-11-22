"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

import { useToast } from "@/components/Toast";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardGridSkeleton,
  Skeleton,
} from "@/components/ui";
import { apiFetch, type BillingUsage, type PlanInfo } from "@/lib/api";
import { mapApiError } from "@/lib/errors";

export default function BillingPage() {
  const { data: session } = useSession();
  const { showToast } = useToast();
  const token = session?.accessToken;
  const [plans, setPlans] = useState<PlanInfo[]>([]);
  const [usage, setUsage] = useState<BillingUsage | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyPlan, setBusyPlan] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    const [planList, me] = await Promise.all([
      apiFetch<PlanInfo[]>("/billing/plans", token),
      apiFetch<BillingUsage>("/billing/me", token),
    ]);
    setPlans(planList);
    setUsage(me);
  }, [token]);

  useEffect(() => {
    load().catch((err: unknown) => {
      const mapped = mapApiError(err, "Could not load billing details.");
      setError(mapped.message);
    });
    const params = new URLSearchParams(window.location.search);
    if (params.get("checkout") === "success") {
      setNotice("Subscription updated. Changes appear once billing confirms.");
    }
    if (params.get("checkout") === "cancelled") {
      setNotice("Checkout cancelled.");
    }
  }, [load]);

  async function startCheckout(planId: "creator" | "pro") {
    setBusyPlan(planId);
    setError(null);
    try {
      const res = await apiFetch<{ url: string }>("/billing/checkout", token, {
        method: "POST",
        body: JSON.stringify({ plan: planId }),
      });
      window.location.assign(res.url);
    } catch (err) {
      const mapped = mapApiError(err, "Could not start checkout.");
      setError(mapped.message);
      showToast({ title: mapped.title, message: mapped.message, tone: "error" });
      setBusyPlan(null);
    }
  }

  async function openPortal() {
    setBusyPlan("portal");
    setError(null);
    try {
      const res = await apiFetch<{ url: string }>("/billing/portal", token, { method: "POST" });
      window.location.assign(res.url);
    } catch (err) {
      const mapped = mapApiError(err, "Could not open billing portal.");
      setError(mapped.message);
      showToast({ title: mapped.title, message: mapped.message, tone: "error" });
      setBusyPlan(null);
    }
  }

  if (error && !usage) {
    return <Alert tone="error">{error}</Alert>;
  }

  if (!token || !usage) {
    return (
      <div className="space-y-6" aria-busy="true" aria-label="Loading billing">
        <Skeleton className="h-8 w-44" />
        <Skeleton className="h-24 w-full" />
        <CardGridSkeleton count={3} />
      </div>
    );
  }

  const videoPct = Math.min(100, Math.round((usage.videos_used / usage.plan.videos_per_month) * 100));
  const minPct = Math.min(100, Math.round((usage.minutes_used / usage.plan.minutes_per_month) * 100));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Billing &amp; usage</h1>
          <p className="text-sm text-ink-muted">
            Current plan: <span className="font-semibold text-ink">{usage.plan.name}</span> (
            {usage.plan.max_resolution}
            {usage.plan.watermark ? ", watermarked" : ", no watermark"})
          </p>
        </div>
        {usage.has_subscription && usage.billing_configured && (
          <Button variant="ghost" onClick={openPortal} loading={busyPlan === "portal"}>
            {busyPlan === "portal" ? "Opening..." : "Manage subscription"}
          </Button>
        )}
      </div>

      {notice && <Alert tone="success">{notice}</Alert>}
      {error && <Alert tone="error">{error}</Alert>}
      {!usage.billing_configured && (
        <Alert tone="info">
          Upgrades are temporarily unavailable. You can continue using your current {usage.plan.name} plan.
        </Alert>
      )}

      <Card className="grid gap-5 sm:grid-cols-2">
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-ink">
            <span>Videos this month</span>
            <span className="font-medium">
              {usage.videos_used} / {usage.plan.videos_per_month}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-surface-muted">
            <div className="h-full bg-brand" style={{ width: `${videoPct}%` }} />
          </div>
        </div>
        <div className="space-y-2">
          <div className="flex justify-between text-sm text-ink">
            <span>Minutes processed</span>
            <span className="font-medium">
              {usage.minutes_used.toFixed(1)} / {usage.plan.minutes_per_month}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-surface-muted">
            <div className="h-full bg-brand" style={{ width: `${minPct}%` }} />
          </div>
        </div>
      </Card>

      <section className="grid gap-5 md:grid-cols-3">
        {plans.map((plan) => {
          const isCurrent = plan.id === usage.plan.id;
          const showUpgrade = !isCurrent && plan.id !== "free" && usage.billing_configured && plan.purchasable;
          return (
            <Card key={plan.id} highlight={isCurrent} className="flex flex-col gap-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="text-lg font-bold text-ink">{plan.name}</h2>
                  <p className="mt-1 text-3xl font-black text-ink">
                    ${plan.price_usd}
                    <span className="text-sm font-normal text-ink-muted">/mo</span>
                  </p>
                </div>
                {isCurrent && <Badge tone="brand">Current</Badge>}
                {!isCurrent && plan.id === "creator" && <Badge tone="neutral">Popular</Badge>}
              </div>
              <ul className="space-y-1.5 text-sm text-ink-muted">
                <li>
                  {plan.videos_per_month} {plan.videos_per_month === 1 ? "video" : "videos"} / month
                </li>
                <li>{plan.minutes_per_month} source minutes / month</li>
                {plan.features.map((feat) => (
                  <li key={feat}>· {feat}</li>
                ))}
              </ul>
              <div className="mt-auto">
                {isCurrent ? (
                  <span className="btn-ghost w-full cursor-default text-center">Current plan</span>
                ) : showUpgrade ? (
                  <Button
                    fullWidth
                    loading={busyPlan === plan.id}
                    disabled={busyPlan !== null}
                    onClick={() => startCheckout(plan.id as "creator" | "pro")}
                  >
                    {busyPlan === plan.id ? "Redirecting..." : `Upgrade to ${plan.name}`}
                  </Button>
                ) : null}
              </div>
            </Card>
          );
        })}
      </section>
    </div>
  );
}
