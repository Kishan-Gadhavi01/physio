import React, { useState } from 'react';
// --- FIX: Corrected import paths ---
// Assuming the components are in 'src/components/'
// and this file is in 'src/pages/'
import Sidebar from '../components/Sidebar.jsx';
import Dashboard from '../components/Dashboard.jsx';
import './Home.css';
import CombinedAnalysis from '../components/CombinedAnalysis.jsx'; // Import the new component

// -----------------------------------

// In a real app, you might get this from a config or API
const availableDashboards = [
 
   { id: 'CombinedAnalysis', name: 'CombinedAnalysis' }
        
];

function Home() {
  const [activeDashboard, setActiveDashboard] = useState('track-me'); // Default to the new one

  const renderActiveDashboard = () => {
    switch (activeDashboard) {
      
     case 'CombinedAnalysis':
        return <CombinedAnalysis />;
     
      default:
        return <CombinedAnalysis />; // Default to the new live one
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