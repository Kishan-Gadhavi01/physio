import React from 'react';
import './Sidebar.css';

// --- ICONS (Simple SVG components for the sidebar) ---
const IconStream = () => <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="1" fill="red"></circle><path d="M16.8 19.3a9 9 0 1 0-9.6 0"></path><path d="M19.1 16.2a5 5 0 1 0-14.2 0"></path></svg>;
const IconDashboard = () => <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>;
const IconReport = () => <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M8 6h13"></path><path d="M8 12h13"></path><path d="M8 18h13"></path><path d="M3 6h.01"></path><path d="M3 12h.01"></path><path d="M3 18h.01"></path></svg>;

// Helper to select an icon based on the dashboard ID
const getIcon = (id) => {
  if (id.includes('track-me')) return <IconStream />;
  if (id.includes('overview')) return <IconReport />;
  return <IconDashboard />;
}

function Sidebar({ dashboards, activeDashboard, setActiveDashboard }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h1 className="logo">🧘‍♂️ Physio</h1>
      </div>
      <nav className="sidebar-nav">
        <ul>
          {dashboards.map(dash => (
            <li key={dash.id}>
              <a
                href="#"
                className={`nav-item ${activeDashboard === dash.id ? 'active' : ''}`}
                onClick={() => setActiveDashboard(dash.id)}
              >
                {getIcon(dash.id)} {dash.name}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <div className="sidebar-footer">
        <div className="user-profile">
            <div className="user-avatar">PJ</div>
            <div className="user-info">
                <span className="user-name">Kishan M.</span>
                <span className="user-role">Physio User</span>
            </div>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;