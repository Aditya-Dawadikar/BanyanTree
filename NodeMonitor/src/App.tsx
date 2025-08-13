import './App.css'
import IsometricCluster from './components/IsometricCluster.tsx'
import { KPI } from './components/KPI.tsx';
import { Charts } from './components/Charts.tsx';
import { Logs } from './components/Logs.tsx';
import type { NodeInfo } from "./types";
import { ReadsWritesTraffic } from './components/ReadsWritesTraffic.tsx';

const sampleNodes: NodeInfo[] = [
  { id: "node-1", status: "online", role: "follower", term: 12, last_seen: new Date(Date.now() - 5000).toISOString(), latency_ms: 18 },
  { id: "node-2", status: "online", role: "leader", term: 12, last_seen: new Date().toISOString(), latency_ms: 12 },
  { id: "node-3", status: "offline", role: "follower", term: 11, last_seen: new Date(Date.now() - 45000).toISOString(), latency_ms: null },
  { id: "node-4", status: "degraded", role: "follower", term: 12, last_seen: new Date(Date.now() - 8000).toISOString(), latency_ms: 420 },
  { id: "node-5", status: "online", role: "follower", term: 12, last_seen: new Date(Date.now() - 2000).toISOString(), latency_ms: 20 },
  { id: "node-6", status: "online", role: "follower", term: 12, last_seen: new Date(Date.now() - 3000).toISOString(), latency_ms: 30 },
  { id: "node-7", status: "online", role: "follower", term: 12, last_seen: new Date(Date.now() - 1500).toISOString(), latency_ms: 22 },
  { id: "node-8", status: "online", role: "follower", term: 12, last_seen: new Date(Date.now() - 2500).toISOString(), latency_ms: 25 },
  { id: "node-9", status: "online", role: "follower", term: 12, last_seen: new Date(Date.now() - 3500).toISOString(), latency_ms: 28 },
  { id: "node-10", status: "online", role: "follower", term: 12, last_seen: new Date(Date.now() - 2000).toISOString(), latency_ms: 20 },
  { id: "node-11", status: "online", role: "follower", term: 12, last_seen: new Date(Date.now() - 3000).toISOString(), latency_ms: 30 },
  { id: "node-12", status: "online", role: "follower", term: 12, last_seen: new Date(Date.now() - 1500).toISOString(), latency_ms: 22 },
  { id: "node-13", status: "online", role: "follower", term: 12, last_seen: new Date(Date.now() - 2500).toISOString(), latency_ms: 25 },
  { id: "node-14", status: "online", role: "follower", term: 12, last_seen: new Date(Date.now() - 3500).toISOString(), latency_ms: 28 }
];

function App() {

  return (
    <div className='grid grid-cols-2 min-h-screen'>
      <div>
        <KPI />
        <ReadsWritesTraffic />

        <Logs
          items={[
            { ts: new Date().toISOString(), level: "info", msg: "Leader elected", node: "node-2", term: 12 },
            { ts: Date.now() - 20000, level: "warn", msg: "Slow append", node: "node-7", latency_ms: 220 },
            { ts: Date.now() - 40000, level: "error", msg: "Heartbeat timeout", node: "node-3" },
            { ts: Date.now() - 60000, level: "info", msg: "Leader elected", node: "node-2", term: 12 },
            { ts: Date.now() - 80000, level: "warn", msg: "Slow append", node: "node-7", latency_ms: 220 },
            { ts: Date.now() - 100000, level: "error", msg: "Heartbeat timeout", node: "node-3" },
            { ts: Date.now() - 120000, level: "info", msg: "Leader elected", node: "node-2", term: 12 },
            { ts: Date.now() - 140000, level: "warn", msg: "Slow append", node: "node-7", latency_ms: 220 },
            { ts: Date.now() - 160000, level: "error", msg: "Heartbeat timeout", node: "node-3" },
          ]}
        />

        {/* <div className='row-span-1'>
          <KPI/>
        </div>
        <div className='row-span-1'>
          {/* <Charts/> */}
        {/* <ReadsWritesTraffic/> */}
        {/* </div>
        <div className='row-span-1'>
          <Logs/>
        </div>  */}
      </div>
      <div style={{ height: "100vh", overflowY: "scroll" }}>
        <IsometricCluster nodes={sampleNodes} />
      </div>
    </div>
  )
}

export default App
