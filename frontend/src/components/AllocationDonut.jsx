import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';

/**
 * AllocationDonut — a colourful donut chart for allocation breakdowns.
 *
 * Props:
 *   data  — array of { label, value_gbp, percentage, color }
 *
 * Uses a curated multi-colour palette. Largest segment gets the first colour.
 */
function AllocationDonut({ data }) {
  if (!data || data.length === 0) return null;

  // Multi-colour palette — muted tones that work on white bg
  const palette = [
    '#2563EB', '#059669', '#D97706', '#7C3AED', '#DC2626',
    '#0891B2', '#4F46E5', '#EA580C', '#BE185D', '#65A30D',
  ];

  const sorted = [...data].sort((a, b) => b.value_gbp - a.value_gbp);

  const chartData = sorted.map((item, i) => ({
    name: item.label,
    value: item.value_gbp,
    pct: item.percentage,
    fill: palette[i % palette.length],
  }));

  return (
    <div className="allocation-donut">
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Tooltip
            formatter={(value, name, entry) => [
              `£${value.toLocaleString(undefined, { minimumFractionDigits: 2 })} (${entry.payload.pct.toFixed(1)}%)`,
              entry.payload.name,
            ]}
            contentStyle={{
              background: '#fff',
              border: '1px solid #e0e0e0',
              borderRadius: '8px',
              fontSize: '0.85rem',
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
            }}
          />
          <Pie
            data={chartData}
            cx="50%"
            cy="50%"
            innerRadius={65}
            outerRadius={95}
            paddingAngle={1}
            dataKey="value"
            stroke="#fff"
            strokeWidth={2}
          >
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.fill} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

export default AllocationDonut;
