import React from "react";
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    Tooltip,
    Legend,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend);

type TrafficChartProps = {
    title: string;
    dataPoints: number[];
    color: string; // e.g. "rgb(34,197,94)" for green
};

const TrafficChart: React.FC<TrafficChartProps> = ({ title, dataPoints, color }) => {
    const data = {
        labels: Array.from({ length: dataPoints.length }, (_, i) => `${i}s`),
        datasets: [
            {
                label: title,
                data: dataPoints,
                borderColor: color,
                backgroundColor: color.replace("rgb", "rgba").replace(")", ",0.1)"),
                tension: 0.3,
                fill: true,
                pointRadius: 0,
            },
        ],
    };

    return (
        <div className="w-full card p-4">
            <h3 className="text-sm font-medium mb-2">Traffic</h3>
            <div className="w-full h-48">
                <Line
                    data={data}
                    options={{
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                        },
                        scales: {
                            y: { beginAtZero: true },
                        },
                    }}
                />
            </div>
        </div>
    );
};

export const ReadsWritesTraffic: React.FC = () => {
    // Example static data; replace with real-time data
    const reads = [
        5, 8, 12, 9, 15, 13, 17, 20, 22, 25, 24, 27, 30, 28, 25, 23,
        20, 19, 21, 18, 16, 19, 20, 22, 24, 29, 35, 38, 36, 33,
        30, 28, 27, 29, 31, 34, 32, 30, 27, 25, 23, 21, 20, 18, 19, 21, 23, 26, 24, 22,
        20, 18, 17, 16, 15, 17, 19, 20, 18, 16, 20, 22, 24, 29, 35, 38, 36, 33,
        30, 28, 27, 29, 31, 34, 32, 30, 27, 25, 23, 21, 20, 18, 19, 21, 23, 26, 24, 22,
        20, 18, 17, 16, 15, 17, 19, 20, 18, 16, 20, 22, 24, 29, 35, 38, 36, 33,
        30, 28, 27, 29, 31, 34, 32, 30, 27, 25, 23, 21, 20, 18, 19, 21, 23, 26, 24, 22,
        20, 18, 17, 16, 15, 17, 19, 20, 18, 16
    ];

    const writes = [
        2, 3, 5, 4, 8, 6, 9, 7, 10, 12, 11, 14, 15, 14, 13, 11,
        9, 10, 12, 13, 11, 9, 8, 10, 12, 15, 17, 16, 15, 14,
        13, 12, 11, 13, 14, 15, 13, 12, 11, 9, 8, 9, 10, 11, 13, 14, 13, 12, 10, 9,
        8, 8, 9, 10, 11, 12, 13, 12, 11, 9
    ];

    return (
        <section className="p-6">
            <h2 className="mb-3 text-sm font-semibold tracking-wide text-gray-500">
                Traffic
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <TrafficChart title="Reads/sec" dataPoints={reads} color="rgb(34,197,94)" />
                <TrafficChart title="Writes/sec" dataPoints={writes} color="rgb(59,130,246)" />
            </div>
        </section>
    );
};
