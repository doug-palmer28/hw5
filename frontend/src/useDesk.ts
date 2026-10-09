import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "./api";
import type { ApprovalRequest, AuditEvent, CashPosition, RunRecord, Ticket, TicketDetail } from "./types";

/** Everything the board shows, kept fresh by polling the backend. */
export function useDesk(selectedId: number | null) {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [shopToday, setShopToday] = useState("");
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [approvals, setApprovals] = useState<ApprovalRequest[]>([]);
  const [cash, setCash] = useState<CashPosition | null>(null);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [busy, setBusy] = useState(false);
  const [model, setModel] = useState("gpt-6-luna");
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);
  const lastSeq = useRef(0);

  const refreshState = useCallback(async () => {
    const [t, a, b, r] = await Promise.all([api.tickets(), api.approvals(), api.balance(), api.runs()]);
    setTickets(t.tickets);
    setShopToday(t.shop_today);
    setApprovals(a.requests);
    setCash(b);
    setRuns(r.runs);
    setBusy(r.busy);
  }, []);

  const refreshDetail = useCallback(async () => {
    if (selectedId == null) return setDetail(null);
    setDetail(await api.ticket(selectedId));
  }, [selectedId]);

  const polling = useRef(false);
  const pollEvents = useCallback(async () => {
    if (polling.current) return false;      // never run two polls at once
    polling.current = true;
    try {
      const res = await api.events(lastSeq.current);
      setModel(res.model);
      setBusy(res.busy);
      const fresh = res.events.filter((e) => e.seq > lastSeq.current);
      if (!fresh.length) return false;
      lastSeq.current = fresh[fresh.length - 1].seq;
      setEvents((prev) => {
        const top = prev.length ? prev[prev.length - 1].seq : 0;
        return [...prev, ...fresh.filter((e) => e.seq > top)];   // append each seq exactly once
      });
      return true;
    } finally {
      polling.current = false;
    }
  }, []);

  const tick = useCallback(async () => {
    try {
      const fresh = await pollEvents();
      if (fresh) await Promise.all([refreshState(), refreshDetail()]);
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, [pollEvents, refreshState, refreshDetail]);

  // First load, then keep polling: fast while the team works, slower when idle.
  useEffect(() => {
    tick().then(() => refreshState().catch(() => setOnline(false)));
  }, [tick, refreshState]);

  useEffect(() => {
    const id = window.setInterval(tick, busy ? 900 : 2500);
    return () => window.clearInterval(id);
  }, [tick, busy]);

  useEffect(() => {
    const id = window.setInterval(() => refreshState().catch(() => setOnline(false)), 6000);
    return () => window.clearInterval(id);
  }, [refreshState]);

  useEffect(() => {
    refreshDetail().catch(() => undefined);
  }, [refreshDetail]);

  // Only events since the most recent database reset belong to the current "shop day".
  const current = useMemo(() => {
    let cut = 0;
    for (const e of events) if (e.event === "db_reset") cut = e.seq;
    return events.filter((e) => e.seq > cut);
  }, [events]);

  const refreshNow = useCallback(async () => {
    await tick();
    await Promise.all([refreshState(), refreshDetail()]);
  }, [tick, refreshState, refreshDetail]);

  return { tickets, shopToday, events: current, approvals, cash, runs, busy, model, detail, online, refreshNow };
}

/** Smoothly animate a number toward its target (used for the checking balance). */
export function useAnimatedNumber(target: number | null, ms = 1400): number | null {
  const [value, setValue] = useState(target);
  const shown = useRef(target);           // what's on screen right now (even mid-animation)
  useEffect(() => {
    if (target == null) return;
    if (shown.current == null) {
      shown.current = target;
      setValue(target);
      return;
    }
    const start = performance.now();
    const a = shown.current;
    let raf = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / ms);
      const eased = 1 - Math.pow(1 - t, 3);
      shown.current = a + (target - a) * eased;
      setValue(shown.current);
      if (t < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    // Animation frames pause in hidden tabs; make sure the number still lands on the real value.
    const land = window.setTimeout(() => {
      cancelAnimationFrame(raf);
      shown.current = target;
      setValue(target);
    }, ms + 60);
    return () => {
      cancelAnimationFrame(raf);
      window.clearTimeout(land);
    };
  }, [target, ms]);
  return value;
}
