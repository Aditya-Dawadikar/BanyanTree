export type NodeStatus = "online" | "offline" | "degraded";

export interface NodeInfo {
  id: string;
  url?: string;
  role?: "leader" | "follower" | "candidate";
  term?: number;
  last_seen?: string;        // ISO
  latency_ms?: number | null;
  status: NodeStatus;
}
