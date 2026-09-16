import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import { HandoffPage } from "./pages/HandoffPage";
import { RadarPage } from "./pages/RadarPage";
import { OpportunitiesPage } from "./pages/OpportunitiesPage";
import { OpportunityDetailPage } from "./pages/OpportunityDetailPage";
import { WatchlistPage } from "./pages/WatchlistPage";
import { DealsPage } from "./pages/DealsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { getTenantId } from "./tenant";

export function App() {
  useLocation();
  const tenant = getTenantId();
  return (
    <div className="app-shell">
      <nav>
        <p>Acquisition Radar</p>
        <NavLink to="/">Radar</NavLink>
        <NavLink to="/opportunities">Opportunities</NavLink>
        <NavLink to="/watchlist">Watchlist</NavLink>
        <NavLink to="/deals">Deals</NavLink>
        <NavLink to="/settings">Settings</NavLink>
        {!tenant ? <p>Open this product from the Aptria Customer Portal.</p> : null}
      </nav>
      <main>
        <Routes>
          <Route path="/handoff" element={<HandoffPage />} />
          <Route path="/" element={<RadarPage />} />
          <Route path="/opportunities" element={<OpportunitiesPage />} />
          <Route path="/opportunities/:id" element={<OpportunityDetailPage />} />
          <Route path="/watchlist" element={<WatchlistPage />} />
          <Route path="/deals" element={<DealsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}
