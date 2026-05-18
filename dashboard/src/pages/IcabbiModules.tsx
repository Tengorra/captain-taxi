import ModulePage from '../components/ModulePage'
import { api } from '../lib/api'

// ─── MANAGE-tab modules ─────────────────────────────────────────────────────

export function Addresses() {
  return <ModulePage
    title="Addresses"
    description="Named address book (per-customer or global landmarks)."
    fields={[
      { key: 'label',        label: 'Label',        type: 'text' },
      { key: 'line1',        label: 'Line 1',       type: 'text', required: true },
      { key: 'line2',        label: 'Line 2',       type: 'text' },
      { key: 'city',         label: 'City',         type: 'text' },
      { key: 'postal',       label: 'Postal',       type: 'text' },
      { key: 'lat',          label: 'Latitude',     type: 'number' },
      { key: 'lng',          label: 'Longitude',    type: 'number' },
      { key: 'address_type', label: 'Type',         type: 'select', options: ['home', 'work', 'landmark', 'other'] },
      { key: 'customer_id',  label: 'Customer ID',  type: 'text' },
    ]}
    columns={[
      { key: 'id', label: 'ID' },
      { key: 'label', label: 'Label' },
      { key: 'line1', label: 'Line 1' },
      { key: 'city', label: 'City' },
      { key: 'address_type', label: 'Type' },
    ]}
    list={() => api.listAddresses()}
    create={(d) => api.createAddress(d)}
    remove={(id) => api.deleteAddress(id)}
  />
}

export function Areas() {
  return <ModulePage
    title="Areas"
    description="Geofenced zones — fare zones, dispatch areas, driver coverage."
    fields={[
      { key: 'name',       label: 'Name',       type: 'text', required: true },
      { key: 'area_type',  label: 'Shape',      type: 'select', options: ['circle', 'polygon'] },
      { key: 'city',       label: 'City',       type: 'text' },
      { key: 'center_lat', label: 'Center Lat', type: 'number' },
      { key: 'center_lng', label: 'Center Lng', type: 'number' },
      { key: 'radius_m',   label: 'Radius (m)', type: 'number' },
      { key: 'active',     label: 'Active',     type: 'bool' },
    ]}
    columns={[
      { key: 'id', label: 'ID' },
      { key: 'name', label: 'Name' },
      { key: 'area_type', label: 'Shape' },
      { key: 'city', label: 'City' },
      { key: 'radius_m', label: 'Radius (m)' },
      { key: 'active', label: 'Active', format: v => v ? 'Yes' : 'No' },
    ]}
    list={() => api.listAreas()}
    create={(d) => api.createArea(d)}
    remove={(id) => api.deleteArea(id)}
  />
}

export function CustomFields() {
  return <ModulePage
    title="Custom Fields"
    description="Define extra fields on Driver / Customer / Trip / Account / Vehicle."
    fields={[
      { key: 'entity_type', label: 'Entity', type: 'select',
        options: ['driver', 'customer', 'trip', 'account', 'vehicle'], required: true },
      { key: 'key',       label: 'Key',       type: 'text', required: true, placeholder: 'e.g. preferred_driver' },
      { key: 'label',     label: 'Label',     type: 'text', required: true },
      { key: 'data_type', label: 'Type',      type: 'select', options: ['string', 'number', 'bool', 'date', 'select'] },
      { key: 'required',  label: 'Required',  type: 'bool' },
    ]}
    columns={[
      { key: 'id', label: 'ID' },
      { key: 'entity_type', label: 'Entity' },
      { key: 'key', label: 'Key' },
      { key: 'label', label: 'Label' },
      { key: 'data_type', label: 'Type' },
      { key: 'required', label: 'Required', format: v => v ? 'Yes' : 'No' },
    ]}
    list={() => api.listFieldDefs()}
    create={(d) => api.createFieldDef(d)}
    remove={(id) => api.deleteFieldDef(id)}
  />
}

export function Favourites() {
  return <ModulePage
    title="Favourites"
    description="Per-customer saved pickup / dropoff locations."
    fields={[
      { key: 'customer_id',  label: 'Customer ID', type: 'text', required: true },
      { key: 'label',        label: 'Label',       type: 'text', required: true },
      { key: 'address_text', label: 'Address',     type: 'text', required: true },
      { key: 'lat',          label: 'Latitude',    type: 'number' },
      { key: 'lng',          label: 'Longitude',   type: 'number' },
    ]}
    columns={[
      { key: 'id', label: 'ID' },
      { key: 'customer_id', label: 'Customer' },
      { key: 'label', label: 'Label' },
      { key: 'address_text', label: 'Address' },
      { key: 'times_used', label: 'Used' },
    ]}
    list={() => api.listFavourites()}
    create={(d) => api.createFavourite(d)}
    remove={(id) => api.deleteFavourite(id)}
  />
}

export function Items() {
  return <ModulePage
    title="Items"
    description="Trip extras catalogue — cleaning fee, child seat, meet-and-greet, etc."
    fields={[
      { key: 'code',        label: 'Code',        type: 'text', required: true, placeholder: 'e.g. CLEAN_FEE' },
      { key: 'name',        label: 'Name',        type: 'text', required: true },
      { key: 'description', label: 'Description', type: 'text' },
      { key: 'price',       label: 'Price',       type: 'number', required: true },
      { key: 'taxable',     label: 'Taxable',     type: 'bool' },
      { key: 'active',      label: 'Active',      type: 'bool' },
    ]}
    columns={[
      { key: 'code', label: 'Code' },
      { key: 'name', label: 'Name' },
      { key: 'price', label: 'Price', format: v => `$${Number(v).toFixed(2)}` },
      { key: 'taxable', label: 'Taxable', format: v => v ? 'Yes' : 'No' },
      { key: 'active', label: 'Active', format: v => v ? 'Yes' : 'No' },
    ]}
    list={() => api.listItems()}
    create={(d) => api.createItem(d)}
    remove={(id) => api.deleteItem(id)}
  />
}

export function Partners() {
  return <ModulePage
    title="Partners"
    description="Affiliate operators — sister taxi companies, ride-share handoff partners."
    fields={[
      { key: 'name',            label: 'Name',          type: 'text', required: true },
      { key: 'contact_name',    label: 'Contact',       type: 'text' },
      { key: 'contact_phone',   label: 'Phone',         type: 'text' },
      { key: 'contact_email',   label: 'Email',         type: 'text' },
      { key: 'city',            label: 'City',          type: 'text' },
      { key: 'commission_rate', label: 'Commission',    type: 'number', placeholder: '0.10' },
      { key: 'active',          label: 'Active',        type: 'bool' },
    ]}
    columns={[
      { key: 'id', label: 'ID' },
      { key: 'name', label: 'Name' },
      { key: 'contact_phone', label: 'Phone' },
      { key: 'city', label: 'City' },
      { key: 'commission_rate', label: 'Commission', format: v => `${Math.round(Number(v) * 100)}%` },
      { key: 'active', label: 'Active', format: v => v ? 'Yes' : 'No' },
    ]}
    list={() => api.listPartners()}
    create={(d) => api.createPartner(d)}
    remove={(id) => api.deletePartner(id)}
  />
}

// ─── ADMIN-tab modules ──────────────────────────────────────────────────────

export function Blacklist() {
  return <ModulePage
    title="Blacklist"
    description="Blocked phone numbers, customers, drivers, or emails."
    fields={[
      { key: 'entity_type',  label: 'Block Type', type: 'select',
        options: ['phone', 'customer', 'driver', 'email'], required: true },
      { key: 'entity_value', label: 'Value',      type: 'text', required: true },
      { key: 'reason',       label: 'Reason',     type: 'text', required: true },
      { key: 'added_by',     label: 'Added By',   type: 'text', placeholder: 'owner' },
    ]}
    columns={[
      { key: 'id', label: 'ID' },
      { key: 'entity_type', label: 'Type' },
      { key: 'entity_value', label: 'Value' },
      { key: 'reason', label: 'Reason' },
      { key: 'added_by', label: 'By' },
      { key: 'expires_at', label: 'Expires' },
    ]}
    list={() => api.listBlacklist()}
    create={(d) => api.addBlacklist(d)}
    remove={(id) => api.removeBlacklist(id)}
  />
}

export function Receipts() {
  return <ModulePage
    title="Receipts"
    description="Customer trip receipts (generated PDFs, sent by email)."
    fields={[
      { key: 'trip_id',       label: 'Trip ID',     type: 'text', required: true },
      { key: 'customer_id',   label: 'Customer ID', type: 'text' },
      { key: 'subtotal',      label: 'Subtotal',    type: 'number' },
      { key: 'tax',           label: 'Tax',         type: 'number' },
      { key: 'total',         label: 'Total',       type: 'number' },
      { key: 'sent_to_email', label: 'Send To',     type: 'text' },
    ]}
    columns={[
      { key: 'id', label: 'ID', format: v => v ? `#${v}` : '—' },
      { key: 'trip_id', label: 'Trip' },
      { key: 'total', label: 'Total', format: v => `$${Number(v).toFixed(2)}` },
      { key: 'sent_to_email', label: 'Email' },
      { key: 'sent_at', label: 'Sent' },
      { key: 'id', label: 'PDF', format: v => v
        ? <a href={api.receiptPdfUrl(v)} target="_blank" rel="noopener"
             className="text-amber-400 hover:underline">Download</a>
        : '—' },
    ]}
    list={() => api.listReceipts()}
    create={(d) => api.createReceipt(d)}
  />
}

export function OwnerStatements() {
  return <ModulePage
    title="Owner Statements"
    description="Per-vehicle-owner periodic payout statements (distinct from driver pay)."
    fields={[
      { key: 'owner_name',   label: 'Owner Name',  type: 'text', required: true },
      { key: 'owner_email',  label: 'Owner Email', type: 'text' },
      { key: 'vehicle_ref',  label: 'Vehicle Ref', type: 'text', placeholder: 'e.g. t1000' },
      { key: 'period_start', label: 'Period Start', type: 'text', placeholder: 'YYYY-MM-DD', required: true },
      { key: 'period_end',   label: 'Period End',   type: 'text', placeholder: 'YYYY-MM-DD', required: true },
      { key: 'gross',        label: 'Gross',       type: 'number' },
      { key: 'deductions',   label: 'Deductions',  type: 'number' },
      { key: 'net',          label: 'Net',         type: 'number' },
    ]}
    columns={[
      { key: 'id', label: 'ID' },
      { key: 'owner_name', label: 'Owner' },
      { key: 'vehicle_ref', label: 'Vehicle' },
      { key: 'period_start', label: 'From' },
      { key: 'period_end', label: 'To' },
      { key: 'net', label: 'Net', format: v => `$${Number(v).toFixed(2)}` },
      { key: 'status', label: 'Status' },
      { key: 'id', label: 'PDF', format: v => v
        ? <a href={api.ownerStatementPdfUrl(v)} target="_blank" rel="noopener"
             className="text-amber-400 hover:underline">Download</a>
        : '—' },
    ]}
    list={() => api.listOwnerStatements()}
    create={(d) => api.createOwnerStatement(d)}
    headerExtra={(reload) => (
      <button
        onClick={async () => {
          try {
            const r = await api.generateOwnerStatements()
            alert(`Generated ${r.created_count} statement(s) for ${r.period_start} → ${r.period_end}\n` +
                  `Skipped (already exist): ${r.skipped_count}`)
            reload()
          } catch (e: any) {
            alert(`Failed: ${e?.message || e}`)
          }
        }}
        className="bg-gray-800 hover:bg-gray-700 text-gray-200 border border-gray-700 px-3 py-2 rounded-lg text-xs font-medium"
        title="Roll up completed trips for last calendar month into draft statements"
      >
        Generate last month
      </button>
    )}
  />
}

export function Staff() {
  return <ModulePage
    title="Staff"
    description="Dashboard login accounts — owner, Amara, optional read-only users."
    fields={[
      { key: 'email',     label: 'Email',  type: 'text', required: true },
      { key: 'name',      label: 'Name',   type: 'text', required: true },
      { key: 'phone',     label: 'Phone',  type: 'text' },
      { key: 'role',      label: 'Role',   type: 'select', options: ['owner', 'admin', 'viewer'] },
      { key: 'is_active', label: 'Active', type: 'bool' },
    ]}
    columns={[
      { key: 'id', label: 'ID' },
      { key: 'name', label: 'Name' },
      { key: 'email', label: 'Email' },
      { key: 'role', label: 'Role' },
      { key: 'is_active', label: 'Active', format: v => v ? 'Yes' : 'No' },
      { key: 'last_login_at', label: 'Last Login' },
    ]}
    list={() => api.listStaff()}
    create={(d) => api.createStaff(d)}
    remove={(id) => api.deleteStaff(id)}
  />
}
