import React from "react";

type KPIItem = {
    label: string;
    value: number | string;
    metric?: string | null;  // e.g., "+3 in last min"
    tone?: "green" | "red" | "indigo"; // optional color override
};

const toneMap = {
    green: "bg-emerald-500/90 ring-emerald-500/30 text-emerald-700",
    red: "bg-rose-500/90 ring-rose-500/30 text-rose-700",
    indigo: "bg-indigo-500/90 ring-indigo-500/30 text-indigo-700",
};

export const KPI: React.FC = () => {
    const data: KPIItem[] = [
        { label: "Live Nodes", value: 10, tone: "green", metric: "+2 in last min" },
        { label: "Dead Nodes", value: 3, tone: "red", metric: "stable" },
        { label: "Leader", value: "node-1", tone: "indigo", metric: "term 12" },
    ];

    return (
        <section className="p-6">
            <h2 className="mb-3 text-sm font-semibold tracking-wide text-gray-500">
                Cluster KPIs
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {data.map((item, i) => {
                    const tone = toneMap[item.tone ?? "indigo"];
                    return (
                        <article
                            key={i}
                            className="group rounded-xl border border-gray-200/70 bg-white/80 backdrop-blur shadow-sm transition hover:shadow-md hover:-translate-y-0.5"
                        >
                            <div className="flex items-start gap-3 p-4">
                                {/* colored dot */}
                                <span
                                    aria-hidden
                                    className={`mt-1 h-2.5 w-2.5 rounded-full ring-4 ${tone}`}
                                />

                                {/* content */}
                                <div className="min-w-0">
                                    <div className="text-xs uppercase tracking-wide text-gray-500">
                                        {item.label}
                                    </div>
                                    <div className="mt-1 text-2xl font-semibold text-gray-800 tabular-nums">
                                        {item.value}
                                    </div>
                                    {item.metric ? (
                                        <div className="mt-1 text-xs text-gray-500">{item.metric}</div>
                                    ) : null}
                                </div>
                            </div>

                            {/* bottom accent bar */}
                            <div
                                className={`h-1 w-full rounded-b-xl transition-all group-hover:h-1.5 ${{
                                    green: "bg-emerald-100",
                                    red: "bg-rose-100",
                                    indigo: "bg-indigo-100",
                                }[item.tone ?? "indigo"]}`}
                            />
                        </article>
                    );
                })}
            </div>
        </section>
    );
};
