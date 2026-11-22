"use client";

import { useSession } from "next-auth/react";
import { useCallback, useEffect, useState } from "react";

import { apiFetch, type BillingUsage, type PlanInfo } from "@/lib/api";

export default function BillingPage() {
  const { data: session } = useSession();
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
    load().catch((err: Error) => setError(err.message));
    const params = new URLSearchParams(window.location.search);
    if (params.get("checkout") === "success") {
      setNotice("Subscription updated. Changes appear once Stripe confirms the webhook.");
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
      setError(err instanceof Error ? err.message : "Could not open Stripe Checkout.");
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
      setError(err instanceof Error ? err.message : "Could not open billing portal.");
      setBusyPlan(null);
    }
  }

  if (!token || !usage) return <p className="text-neutral-400">Loading billing...</p>;

  const videoPct = Math.min(100, Math.round((usage.videos_used / usage.plan.videos_per_month) * 100));
  const minPct = Math.min(100, Math.round((usage.minutes_used / usage.plan.minutes_per_month) * 100));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Billing &amp; usage</h1>
          <p className="text-sm text-neutral-400">
            Current plan: <span className="font-semibold text-white">{usage.plan.name}</span> (
            {usage.plan.max_resolution}
            {usage.plan.watermark ? ", watermarked" : ", no watermark"})
          </p>
        </div>
        {usage.has_subscription && (
          <button className="btn-ghost" onClick={openPortal} disabled={busyPlan === "portal"}>
            {busyPlan === "portal" ? "Opening..." : "Manage subscription"}
          </button>
        )}
      </div>

      {notice && <p className="text-sm text-emerald-300">{notice}</p>}
      {error && <p className="text-sm text-red-400">{error}</p>}
      {!usage.billing_configured && (
        <p className="card text-sm text-yellow-300">
          Stripe is not configured on this server. Set SNIPZO_STRIPE_SECRET_KEY,
          SNIPZO_STRIPE_WEBHOOK_SECRET, SNIPZO_STRIPE_PRICE_CREATOR, and SNIPZO_STRIPE_PRICE_PRO
          to enable upgrades.
        </p>
      )}

      <section className="card grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Videos this month</span>
            <span>
              {usage.videos_used} / {usage.plan.videos_per_month}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-neutral-800">
            <div className="h-full bg-brand" style={{ width: `${videoPct}%` }} />
          </div>
        </div>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span>Minutes processed</span>
            <span>
              {usage.minutes_used.toFixed(1)} / {usage.plan.minutes_per_month}
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-neutral-800">
            <div className="h-full bg-brand" style={{ width: `${minPct}%` }} />
          </div>
        </div>
      </section>

      <section className="grid gap-5 md:grid-cols-3">
        {plans.map((plan) => {
          const isCurrent = plan.id === usage.plan.id;
          return (
            <div
              key={plan.id}
              className={`card flex flex-col gap-4 ${isCurrent ? "border-brand" : ""}`}
            >
              <div>
                <h2 className="text-lg font-bold">{plan.name}</h2>
                <p className="mt-1 text-3xl font-black">
                  ${plan.price_usd}
                  <span className="text-sm font-normal text-neutral-400">/mo</span>
                </p>
              </div>
              <ul className="space-y-1 text-sm text-neutral-300">
                <li>{plan.videos_per_month} videos / month</li>
                <li>{plan.minutes_per_month} source minutes / month</li>
                {plan.features.map((feat) => (
                  <li key={feat}>· {feat}</li>
                ))}
              </ul>
              <div className="mt-auto">
                {isCurrent ? (
                  <span className="btn-ghost w-full cursor-default text-center">Current plan</span>
                ) : plan.id === "free" ? null : (
                  <button
                    className="btn w-full"
                    disabled={!plan.purchasable || busyPlan !== null}
                    onClick={() => startCheckout(plan.id as "creator" | "pro")}
                  >
                    {busyPlan === plan.id ? "Redirecting..." : `Upgrade to ${plan.name}`}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </section>
    </div>
  );
}
