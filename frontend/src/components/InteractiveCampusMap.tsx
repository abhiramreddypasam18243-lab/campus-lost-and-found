import React, { useState } from 'react'

export interface CampusBuilding {
  id: string
  name: string
  shortCode: string
  category: string
  itemCount: number
  x: number
  y: number
  width: number
  height: number
  color: string
  floors: string[]
}

const CAMPUS_BUILDINGS: CampusBuilding[] = [
  {
    id: 'bldg-library',
    name: 'Central University Library',
    shortCode: 'LIB',
    category: 'Academic & Study',
    itemCount: 4,
    x: 60,
    y: 70,
    width: 220,
    height: 140,
    color: '#3b82f6',
    floors: ['Floor 1 (Circulation Desk)', 'Floor 2 (Quiet Study)', 'Reading Room'],
  },
  {
    id: 'bldg-science',
    name: 'Science & Innovation Complex',
    shortCode: 'SCI',
    category: 'STEM Laboratories',
    itemCount: 3,
    x: 340,
    y: 60,
    width: 200,
    height: 150,
    color: '#06b6d4',
    floors: ['Floor 1 (Atrium)', 'Floor 2 (Biotech Labs)', 'Lab 101'],
  },
  {
    id: 'bldg-engineering',
    name: 'Engineering & Robotics Center',
    shortCode: 'ENG',
    category: 'Engineering Workshops',
    itemCount: 2,
    x: 600,
    y: 80,
    width: 190,
    height: 130,
    color: '#8b5cf6',
    floors: ['Ground Workshop', 'Lab A (Mechatronics)', 'Lab B (Computing)'],
  },
  {
    id: 'bldg-union',
    name: 'Student Union & Dining Hall',
    shortCode: 'STU',
    category: 'Social & Cafeteria',
    itemCount: 5,
    x: 100,
    y: 280,
    width: 240,
    height: 150,
    color: '#10b981',
    floors: ['Cafeteria Main Hall', 'Student Lounge', 'Club Activity Rooms'],
  },
  {
    id: 'bldg-admin',
    name: 'University Administration',
    shortCode: 'ADM',
    category: 'Administration & Security',
    itemCount: 1,
    x: 400,
    y: 270,
    width: 170,
    height: 160,
    color: '#f59e0b',
    floors: ['Floor 1 (Security Central)', 'Auditorium', 'Lost & Found Vault'],
  },
  {
    id: 'bldg-sports',
    name: 'Sports Arena & Gymnasium',
    shortCode: 'SPT',
    category: 'Athletics & Recreation',
    itemCount: 2,
    x: 630,
    y: 270,
    width: 180,
    height: 150,
    color: '#ec4899',
    floors: ['Indoor Basketball Court', 'Fitness Center', 'Locker Rooms'],
  },
]

interface InteractiveCampusMapProps {
  onSelectLocation?: (locationName: string) => void
  selectedLocation?: string
}

export const InteractiveCampusMap: React.FC<InteractiveCampusMapProps> = ({
  onSelectLocation,
  selectedLocation,
}) => {
  const [activeBuilding, setActiveBuilding] = useState<CampusBuilding | null>(
    CAMPUS_BUILDINGS[0]
  )
  const [selectedFloor, setSelectedFloor] = useState<string>(CAMPUS_BUILDINGS[0].floors[0])

  const handleBuildingClick = (bldg: CampusBuilding) => {
    setActiveBuilding(bldg)
    setSelectedFloor(bldg.floors[0])
    if (onSelectLocation) {
      onSelectLocation(`${bldg.name} - ${bldg.floors[0]}`)
    }
  }

  const handleFloorSelect = (floor: string) => {
    setSelectedFloor(floor)
    if (activeBuilding && onSelectLocation) {
      onSelectLocation(`${activeBuilding.name} - ${floor}`)
    }
  }

  return (
    <div className="campus-map-container" role="region" aria-label="Interactive Campus Map">
      <div className="campus-map-header">
        <div>
          <h3 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
            🗺️ Interactive Campus Map &amp; Spatial Density
          </h3>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', margin: '0.2rem 0 0 0' }}>
            Click on any campus building to view recovered items, inspect floors, or select your location.
          </p>
        </div>
        {selectedLocation && (
          <div className="selected-loc-chip">
            <span>📍 Selected: <strong>{selectedLocation}</strong></span>
          </div>
        )}
      </div>

      <div className="campus-map-layout">
        {/* SVG Blueprint Canvas */}
        <div className="map-canvas-wrapper">
          <svg
            viewBox="0 0 860 480"
            className="campus-svg-canvas"
            aria-label="Campus architectural layout map"
          >
            {/* Campus Ground / Paths */}
            <rect x="0" y="0" width="860" height="480" rx="12" fill="#0f172a" />
            <defs>
              <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
                <path d="M 30 0 L 0 0 0 30" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
              </pattern>
            </defs>
            <rect x="0" y="0" width="860" height="480" fill="url(#grid)" />

            {/* Walking Plazas / Campus Walkways */}
            <path
              d="M 50 240 Q 430 230 810 240 M 310 50 L 310 440 M 575 50 L 575 440"
              stroke="rgba(59, 130, 246, 0.2)"
              strokeWidth="18"
              fill="none"
              strokeDasharray="6 6"
            />

            {/* Central Campus Lawn */}
            <circle cx="430" cy="235" r="35" fill="rgba(16, 185, 129, 0.15)" stroke="#10b981" strokeWidth="1.5" strokeDasharray="3 3" />
            <text x="430" y="239" textAnchor="middle" fill="#6ee7b7" fontSize="10" fontWeight="600">
              CAMPUS QUAD
            </text>

            {/* Buildings */}
            {CAMPUS_BUILDINGS.map((bldg) => {
              const isSelected = activeBuilding?.id === bldg.id
              return (
                <g
                  key={bldg.id}
                  className={`map-building-group ${isSelected ? 'active' : ''}`}
                  onClick={() => handleBuildingClick(bldg)}
                  style={{ cursor: 'pointer' }}
                >
                  {/* Building shadow/glow */}
                  <rect
                    x={bldg.x}
                    y={bldg.y}
                    width={bldg.width}
                    height={bldg.height}
                    rx="8"
                    fill={isSelected ? `${bldg.color}33` : 'rgba(30, 41, 59, 0.85)'}
                    stroke={isSelected ? bldg.color : 'rgba(148, 163, 184, 0.25)'}
                    strokeWidth={isSelected ? '2.5' : '1.5'}
                    style={{ transition: 'all 0.2s ease' }}
                  />

                  {/* Building Code Badge */}
                  <rect
                    x={bldg.x + 12}
                    y={bldg.y + 12}
                    width="42"
                    height="22"
                    rx="4"
                    fill={bldg.color}
                  />
                  <text
                    x={bldg.x + 33}
                    y={bldg.y + 27}
                    textAnchor="middle"
                    fill="#ffffff"
                    fontSize="11"
                    fontWeight="800"
                    fontFamily="monospace"
                  >
                    {bldg.shortCode}
                  </text>

                  {/* Building Name */}
                  <text
                    x={bldg.x + 62}
                    y={bldg.y + 27}
                    fill="#f8fafc"
                    fontSize="11.5"
                    fontWeight="700"
                  >
                    {bldg.name.length > 20 ? bldg.name.slice(0, 19) + '…' : bldg.name}
                  </text>

                  {/* Category note */}
                  <text
                    x={bldg.x + 12}
                    y={bldg.y + 58}
                    fill="#94a3b8"
                    fontSize="10"
                  >
                    {bldg.category}
                  </text>

                  {/* Live Item Density Tag */}
                  <rect
                    x={bldg.x + 12}
                    y={bldg.y + bldg.height - 30}
                    width="110"
                    height="18"
                    rx="9"
                    fill="rgba(15, 23, 42, 0.9)"
                    stroke="rgba(255,255,255,0.1)"
                  />
                  <text
                    x={bldg.x + 67}
                    y={bldg.y + bldg.height - 17}
                    textAnchor="middle"
                    fill={bldg.itemCount > 0 ? '#38bdf8' : '#94a3b8'}
                    fontSize="9.5"
                    fontWeight="600"
                  >
                    📦 {bldg.itemCount} items found
                  </text>
                </g>
              )
            })}
          </svg>
        </div>

        {/* Building Details & Floor Selector Drawer */}
        {activeBuilding && (
          <div className="map-sidebar-card">
            <div className="bldg-badge-row">
              <span className="bldg-code-chip" style={{ backgroundColor: activeBuilding.color }}>
                {activeBuilding.shortCode}
              </span>
              <div>
                <h4 style={{ margin: 0, fontSize: '1rem', color: '#fff' }}>{activeBuilding.name}</h4>
                <small style={{ color: 'var(--text-muted)' }}>{activeBuilding.category}</small>
              </div>
            </div>

            <div className="bldg-stat-box">
              <span>Current Recovered Items:</span>
              <strong style={{ color: '#38bdf8', fontSize: '1.1rem' }}>{activeBuilding.itemCount} active</strong>
            </div>

            <div className="floor-selector">
              <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                Select Floor / Specific Zone:
              </label>
              <div className="floor-chips-grid">
                {activeBuilding.floors.map((fl) => (
                  <button
                    key={fl}
                    type="button"
                    className={`floor-btn ${selectedFloor === fl ? 'active' : ''}`}
                    onClick={() => handleFloorSelect(fl)}
                  >
                    {fl}
                  </button>
                ))}
              </div>
            </div>

            {onSelectLocation && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                style={{ width: '100%', marginTop: '0.5rem' }}
                onClick={() => onSelectLocation(`${activeBuilding.name} - ${selectedFloor}`)}
              >
                ✓ Use this Location in Report
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
