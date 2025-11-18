import React, { useState } from 'react';
// --- FIX: Corrected import paths ---
// Assuming the components are in 'src/components/'
// and this file is in 'src/pages/'
import Sidebar from '../components/Sidebar.jsx';
import Dashboard from '../components/Dashboard.jsx';
import StaticDashboard from '../components/StaticDashboard.jsx';
import DataExplorerDashboard from '../components/DataExplorerDashboard.jsx';
import TrackMe from '../components/TrackMe.jsx'; // Import the new component
import './Home.css';
import CombinedAnalysis from '../components/CombinedAnalysis.jsx'; // Import the new component

// -----------------------------------

// In a real app, you might get this from a config or API
const availableDashboards = [
  { id: 'track-me', name: 'Track Me (Live)' }, // Add new dashboard here
  { id: 'session-analysis', name: 'Session Analysis' },
  { id: 'Session-overview', name: 'Session Overview' },
  { id: 'DataExplorerDashboard-overview', name: 'DataExplorerDashboard' },
  { id: 'CombinedAnalysis', name: 'CombinedAnalysis' },


];

function Home() {
  const [activeDashboard, setActiveDashboard] = useState('track-me'); // Default to the new one

  const renderActiveDashboard = () => {
    switch (activeDashboard) {
      case 'track-me':
        return <TrackMe />; // Add the case for it
      case 'session-analysis':
        return <Dashboard />;
      case 'Session-overview':
        return <StaticDashboard />;
      case 'DataExplorerDashboard-overview':
        return <DataExplorerDashboard />;    
      case 'CombinedAnalysis':
        return <CombinedAnalysis />;      
      default:
        return <TrackMe />; // Default to the new live one
    }
  };

  return (
    <div className="home-layout">
      <Sidebar
        dashboards={availableDashboards}
        activeDashboard={activeDashboard}
        setActiveDashboard={setActiveDashboard}
      />
      <main className="workspace">
        {renderActiveDashboard()}
      </main>
    </div>
  );
}

export default Home;