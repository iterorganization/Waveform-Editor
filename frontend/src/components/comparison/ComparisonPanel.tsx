import { useStore } from "../../store";
import { CoilCurrentsChart } from "./CoilCurrentsChart";
import { IpChart } from "./IpChart";
import { ProfilesChart } from "./ProfilesChart";
import { ShapeMetricsChart } from "./ShapeMetricsChart";

const TABS = [
  { label: "Shape metrics", key: 0 },
  { label: "Ip vs time",    key: 1 },
  { label: "Profiles",      key: 2 },
  { label: "Coil currents", key: 3 },
];

export function ComparisonPanel() {
  const { activeComparisonTab, setActiveComparisonTab } = useStore();

  return (
    <div className="comparison-panel">
      <div className="comp-tabs">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            className={`comp-tab ${activeComparisonTab === tab.key ? "active" : ""}`}
            onClick={() => setActiveComparisonTab(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="comp-body">
        {activeComparisonTab === 0 && <ShapeMetricsChart />}
        {activeComparisonTab === 1 && <IpChart />}
        {activeComparisonTab === 2 && <ProfilesChart />}
        {activeComparisonTab === 3 && <CoilCurrentsChart />}
      </div>
    </div>
  );
}
