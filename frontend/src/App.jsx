import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import MainLayout from './layout/MainLayout';
import Dashboard from './pages/Dashboard';
import TeamAnalysis from './pages/TeamAnalysis';
import TransferSuggestions from './pages/TransferSuggestions';
import SimulationMode from './pages/SimulationMode';
import Settings from './pages/Settings';
import { FPLProvider } from './context/FPLContext';

// Placeholder components for other routes
const Placeholder = ({ title }) => (
  <div className="flex items-center justify-center h-full text-gray-500">
    <div className="text-center">
      <h2 className="text-2xl font-bold text-gray-300 mb-2">{title}</h2>
      <p>This feature is coming soon.</p>
    </div>
  </div>
);

function App() {
  return (
    <FPLProvider>
      <Router>
        <MainLayout>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/team" element={<TeamAnalysis />} />
            <Route path="/transfers" element={<TransferSuggestions />} />
            <Route path="/analysis" element={<TeamAnalysis />} /> {/* Reuse for now */}
            <Route path="/simulation" element={<SimulationMode />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </MainLayout>
      </Router>
    </FPLProvider>
  );
}

export default App;
