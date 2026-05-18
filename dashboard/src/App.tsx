import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import Dispatch from './pages/Dispatch'
import Drivers from './pages/Drivers'
import DriverProfile from './pages/DriverProfile'
import Accounts from './pages/Accounts'
import Compliance from './pages/Compliance'
import Reports from './pages/Reports'
import Settings from './pages/Settings'
import {
  Addresses, Areas, CustomFields, Favourites, Items, Partners,
  Blacklist, Receipts, OwnerStatements, Staff,
} from './pages/IcabbiModules'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/overview" replace />} />
          <Route path="overview" element={<Overview />} />
          <Route path="dispatch" element={<Dispatch />} />
          <Route path="drivers" element={<Drivers />} />
          <Route path="drivers/:id" element={<DriverProfile />} />
          <Route path="accounts" element={<Accounts />} />
          <Route path="compliance" element={<Compliance />} />
          <Route path="reports" element={<Reports />} />
          <Route path="settings" element={<Settings />} />

          {/* iCabbi MANAGE-tab modules */}
          <Route path="addresses" element={<Addresses />} />
          <Route path="areas" element={<Areas />} />
          <Route path="custom-fields" element={<CustomFields />} />
          <Route path="favourites" element={<Favourites />} />
          <Route path="items" element={<Items />} />
          <Route path="partners" element={<Partners />} />

          {/* iCabbi ADMIN-tab modules */}
          <Route path="blacklist" element={<Blacklist />} />
          <Route path="receipts" element={<Receipts />} />
          <Route path="owner-statements" element={<OwnerStatements />} />
          <Route path="staff" element={<Staff />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
