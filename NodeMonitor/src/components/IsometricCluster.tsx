import React, { useEffect, useMemo, useState } from "react";
import type { NodeInfo, NodeStatus } from "../types";

type Pt = { x: number; y: number };

const statusColor: Record<NodeStatus, string> = {
    online: "rgba(34,197,94,0.65)",   // green
    degraded: "rgba(234,179,8,0.70)",   // yellow
    offline: "rgba(239,68,68,0.70)",   // red
};

const IsometricCluster: React.FC<{
    nodes: NodeInfo[];
    tileW?: number;
    tileH?: number;
}> = ({ nodes, tileW = 200, tileH = 100 }) => {
    const [hover, setHover] = useState<{ node: NodeInfo; x: number; y: number } | null>(null);
    const positions = useMemo(() => gridLayout(nodes.length), [nodes.length]);

    const anchorX = 45;   // moves the plus left/right relative to the cube origin
    const anchorY = 90;

    function timeAgo(iso?: string) {
        if (!iso) return "—";
        const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
        if (s < 1) return "now";
        if (s < 60) return `${s}s ago`;
        if (s < 3600) return `${Math.floor(s / 60)}m ago`;
        return `${Math.floor(s / 3600)}h ago`;
    }

    function gridLayout(
        n: number,
        cellW: number = 1,
        cellH: number = 1,
        startWithShort = false
    ): Pt[] {
        const pos: Pt[] = [];

        let i = 0;
        let rowIndex = -1;

        while (i < n) {
            // start new row
            rowIndex++;

            const isShortRow = (rowIndex % 2 === 1) !== startWithShort ? false : true;

            const cap = isShortRow ? 3 : 4;
            // const cap = 4
            const offsetX = isShortRow ? cellW / 2 : 0; // center 3 under 4
            // const offsetX = 0;
            const y = rowIndex * cellH;

            for (let col = 0; col < cap && i < n; col++, i++) {
                const x = offsetX + col * cellW;
                pos.push({ x, y });
            }
        }

        return pos;
    }

    const Tooltip: React.FC<{ x: number; y: number; node: NodeInfo }> = ({ x, y, node }) => {

        return (
            <div
                className="pointer-events-none absolute z-50 min-w-[220px] rounded-xl  bg-white/95 backdrop-blur p-3 text-sm shadow-xl"
                style={{ left: x, top: y }}
            >
                <div className="font-semibold text-gray-800 mb-1">{node.id}</div>
                <div className="grid grid-cols-2 gap-x-2 gap-y-1 text-gray-600">
                    <div className="text-gray-500">Role</div>
                    <div className="capitalize">{node.role ?? "—"}</div>
                    <div className="text-gray-500">Term</div>
                    <div>{node.term ?? "—"}</div>
                    <div className="text-gray-500">Last Seen</div>
                    <div>{timeAgo(node.last_seen)}</div>
                    <div className="text-gray-500">Latency</div>
                    <div>{node.latency_ms != null ? `${node.latency_ms} ms` : "—"}</div>
                </div>
            </div>
        )
    };

    const PlusMark: React.FC<{ x: number; y: number; color: string; size?: number }> = ({
        x, y, color
    }) => {
        const thickness = 2;                 // bar thickness
        return (
            <div
                className="pointer-events-none absolute -z-10"
                style={{ left: x, top: y }}
            >
                {/* vertical bar */}
                <span
                    className="line"
                    style={{
                        position: "absolute",
                        left: "5px",
                        top: "-150px",
                        width: thickness,
                        height: 225,
                        background: `linear-gradient(to bottom, 
                        rgba(0,0,0,0), 
                        ${color}, 
                        rgba(0,0,0,0))`,
                        borderRadius: 1,
                    }}
                />
                {/* horizontal bar */}
                <span
                    style={{
                        position: "absolute",
                        left: "-110px",
                        top: "-15px",
                        width: 225,
                        height: thickness,
                        background: `linear-gradient(to right, 
                        rgba(0,0,0,0), 
                        ${color}, 
                        rgba(0,0,0,0))`,
                        borderRadius: 1,
                    }}
                />
            </div>
        );
    };

    const Cube: React.FC<{
        n: any;
        status: NodeStatus;
        leader?: boolean;
        size?: number;
        left: number;
        top: number;
    }> = ({ status, leader, n, left, top }) => {

        return (
            <div className={`cube status-${status} ${leader ? "is-leader" : ""}`}
                onMouseEnter={(e) => setHover({ node: n, x: left, y: top })}
                onMouseMove={(e) => setHover({ node: n, x: left, y: top })}
                onMouseLeave={() => setHover(null)}
            >
                <div className='face front'></div>
                <div className='face side'></div>
                <div className='face top'></div>
                {leader && <div className="leader-flag">▲</div>}
            </div>
        );
    };

    return (
        <div className="relative w-full node-bg">

            {/* node field */}
            <div className="absolute">
                {nodes.map((n, i) => {
                    const left = positions[i].x * tileW + 80;
                    const top = positions[i].y * tileH + 80;
                    return (
                        <div
                            key={n.id}
                            className="absolute"
                            style={{ left, top }}
                        >
                            <PlusMark
                                x={anchorX}
                                y={anchorY}
                                color={statusColor[n.status]}
                            />
                            <div
                                className="cursor-pointer transition-transform hover:-translate-y-1 hover:scale-120">
                                <Cube status={n.status}
                                    leader={n.role === "leader"}
                                    n={n}
                                    left={left}
                                    top={top}
                                />
                            </div>

                            <div className="text-gray-600 node-label">{n.id}</div>
                        </div>
                    );
                })}
            </div>

            {hover && <Tooltip x={hover.x+120} y={hover.y} node={hover.node} />}
        </div>
    );
};

export default IsometricCluster;
