import React, { useEffect, useMemo, useRef, useState } from "react";

type Level = "debug" | "info" | "warn" | "error";

export type LogItem = {
    ts: string | number | Date;   // ISO or epoch
    level: Level;
    msg?: string;
    // any extra fields are fine; they’ll show up in the JSON body
    [key: string]: any;
};

function timeAgo(when: string | number | Date) {
    const t = typeof when === "string" ? new Date(when).getTime()
        : typeof when === "number" ? when : when.getTime();
    const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
    if (s < 1) return "now";
    if (s < 60) return `${s}s ago`;
    if (s < 3600) return `${Math.floor(s / 60)}m ago`;
    return `${Math.floor(s / 3600)}h ago`;
}

const levelStyle: Record<Level, string> = {
    debug: "bg-slate-100 text-slate-700 ring-slate-300/40",
    info: "bg-emerald-100 text-emerald-700 ring-emerald-300/40",
    warn: "bg-amber-100 text-amber-800 ring-amber-300/40",
    error: "bg-rose-100 text-rose-700 ring-rose-300/40",
};

const Caret: React.FC<{ open: boolean }> = ({ open }) => (
    <span
        className={`inline-block transition-transform duration-200 mr-1 select-none ${open ? "rotate-90" : ""
            }`}
    >
        ▸
    </span>
);

export function Logs({
    items,
    follow = true,          // auto-scroll to bottom when new items arrive
    className = "",
}: {
    items: LogItem[];
    follow?: boolean;
    className?: string;
}) {
    const scrollerRef = useRef<HTMLDivElement | null>(null);
    const [openIdx, setOpenIdx] = useState<number | null>(null);

    // Keep scrolled to newest when items change
    useEffect(() => {
        if (!follow || !scrollerRef.current) return;
        scrollerRef.current.scrollTop = scrollerRef.current.scrollHeight;
    }, [items, follow]);

    // Precompute compact header for each log
    const rows = useMemo(
        () =>
            items.map((it, i) => {
                const { level, msg } = it;
                // the header text (fall back to stringify a couple fields)
                const header =
                    msg ??
                    JSON.stringify(
                        Object.fromEntries(
                            Object.entries(it).filter(([k]) => !["ts", "level"].includes(k))
                        )
                    );
                return { i, it, header };
            }),
        [items]
    );

    return (
        <section className={`rounded-xl bg-white/80 backdrop-blur`}>
            <div className="m-2">
                <header className="px-4 py-3">
                    <h2 className="text-sm font-semibold tracking-wide text-gray-600">Cluster Logs</h2>
                </header>

                <div
                    ref={scrollerRef}
                    className="max-h-[42vh] overflow-y-auto"
                    role="log"
                    aria-live="polite"
                >
                    <ul className="divide-y divide-gray-200/70">
                        {rows.map(({ i, it, header }) => {
                            const open = openIdx === i;
                            const json = JSON.stringify(it, null, 2);

                            return (
                                <li key={i} className="group">
                                    {/* Row header */}
                                    <button
                                        onClick={() => setOpenIdx(open ? null : i)}
                                        className="w-full text-left px-3 py-2 flex items-start gap-3 hover:bg-gray-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/50"
                                    >
                                        <Caret open={open} />
                                        <span
                                            className={`px-2 py-0.5 rounded-md text-xs font-medium ring-1 ${levelStyle[it.level]}`}
                                        >
                                            {it.level}
                                        </span>

                                        <span className="flex-1 min-w-0">
                                            <span className="block truncate text-sm text-gray-800">{header}</span>
                                            <span className="block text-[11px] text-gray-500">{timeAgo(it.ts)}</span>
                                        </span>
                                    </button>

                                    {/* Collapsible body */}
                                    {open && (
                                        <div className="px-3 pb-3">
                                            <div className="rounded-lg border border-gray-200 bg-gray-50">
                                                <div className="flex items-center justify-between px-3 py-2">
                                                    <span className="text-xs font-medium text-gray-600">Payload</span>
                                                    <button
                                                        onClick={() => navigator.clipboard.writeText(json)}
                                                        className="text-xs px-2 py-1 rounded-md border border-gray-300 bg-white hover:bg-gray-100"
                                                    >
                                                        Copy JSON
                                                    </button>
                                                </div>
                                                <pre className="px-3 pb-3 pt-1 text-[12px] leading-relaxed text-gray-800 overflow-auto">
                                                    {json}
                                                </pre>
                                            </div>
                                        </div>
                                    )}
                                </li>
                            );
                        })}
                    </ul>
                </div>

                {/* footer controls (optional) */}
                <div className="px-4 py-2 border-t border-gray-200/70 flex items-center gap-3">
                    <label className="flex items-center gap-2 text-xs text-gray-600">
                        <input
                            type="checkbox"
                            className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                            checked={follow}
                            onChange={() => {/* control follow from parent if needed */ }}
                            readOnly
                        />
                        Follow latest
                    </label>
                </div>
            </div>
        </section>
    );
}
