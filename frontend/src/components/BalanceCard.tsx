import { useEffect, useRef, useState } from "react";
import { money } from "../agents";
import { useAnimatedNumber } from "../useDesk";
import type { CashPosition } from "../types";

/** Big checking balance that visibly drops when money goes out the door. */
export function BalanceCard({ cash, paidOut }: { cash: CashPosition | null; paidOut: number }) {
  const balance = cash?.checking.balance ?? null;
  const shown = useAnimatedNumber(balance);
  const prev = useRef<number | null>(null);
  const [drop, setDrop] = useState<{ amount: number; key: number } | null>(null);

  useEffect(() => {
    if (balance == null) return;
    if (prev.current != null && balance < prev.current) {
      setDrop({ amount: prev.current - balance, key: Date.now() });
      const id = window.setTimeout(() => setDrop(null), 4200);
      prev.current = balance;
      return () => window.clearTimeout(id);
    }
    prev.current = balance;
  }, [balance]);

  const start = balance != null ? balance + paidOut : null;
  const pct = start ? Math.max(0, Math.min(100, ((balance ?? 0) / start) * 100)) : 100;

  return (
    <div className={`balance ${drop ? "balance-dropping" : ""}`} aria-live="polite">
      <div className="balance-label">Checking</div>
      <div className="balance-amount">{money(shown)}</div>
      {drop && <div key={drop.key} className="balance-drop">−{money(drop.amount)}</div>}
      <div className="balance-bar" title={`${pct.toFixed(0)}% of today's starting balance`}>
        <span style={{ width: `${pct}%` }} />
      </div>
      <div className="balance-meta">
        <span>Paid out <b>{money(paidOut)}</b></span>
        <span>Waiting <b>{money(cash?.in_flight_total ?? 0)}</b></span>
      </div>
    </div>
  );
}
