import { useEffect } from "react";
import { Header } from "./components/Header";
import { LeftPanel } from "./components/LeftPanel";
import { RightPanel } from "./components/RightPanel";
import { SettingsModal } from "./components/settings/SettingsModal";
import { useStore } from "./store";

export default function App() {
  const { loadSettingsFromServer, parseCurrentYaml, loadMachineGeometries } = useStore();

  useEffect(() => {
    loadSettingsFromServer().then(() => {
      parseCurrentYaml();
      loadMachineGeometries();
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="app-shell">
      <Header />
      <div className="panels">
        <LeftPanel />
        <RightPanel />
      </div>
      <SettingsModal />
    </div>
  );
}
