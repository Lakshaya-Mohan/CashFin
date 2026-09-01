import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, TrendingUp, ShieldCheck, UploadCloud, Building } from 'lucide-react';

export const Navbar = ({ companies = [], selectedCompanyId, onSelectCompany }) => {
  return (
    <header style={{
      background: '#0d131f',
      borderBottom: '1px solid #1f2d42',
      padding: '0.85rem 1.5rem',
      position: 'sticky',
      top: 0,
      zIndex: 100
    }}>
      <div style={{
        maxWidth: '1280px',
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between'
      }}>
        {/* Brand */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{
            background: 'linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%)',
            width: '36px',
            height: '36px',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 'bold',
            color: '#fff',
            fontSize: '1.1rem'
          }}>
            CF
          </div>
          <div>
            <span style={{ fontSize: '1.25rem', fontWeight: '700', color: '#fff', letterSpacing: '-0.02em' }}>CashFin</span>
            <span style={{ fontSize: '0.75rem', color: '#38bdf8', marginLeft: '0.5rem', padding: '0.15rem 0.4rem', background: 'rgba(56, 189, 248, 0.1)', borderRadius: '4px' }}>Pro</span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav style={{ display: 'flex', gap: '0.5rem' }}>
          <NavLink to="/" end className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <LayoutDashboard size={18} />
            <span>Dashboard</span>
          </NavLink>
          <NavLink to="/forecast" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <TrendingUp size={18} />
            <span>Forecast</span>
          </NavLink>
          <NavLink to="/decisions" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <ShieldCheck size={18} />
            <span>Decisions</span>
          </NavLink>
          <NavLink to="/ingestion" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
            <UploadCloud size={18} />
            <span>Ingestion</span>
          </NavLink>
        </nav>

        {/* Company Selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', background: '#172033', padding: '0.4rem 0.8rem', borderRadius: '8px', border: '1px solid #25334c' }}>
          <Building size={16} style={{ color: '#9ca3af' }} />
          <select
            value={selectedCompanyId || ''}
            onChange={(e) => onSelectCompany && onSelectCompany(Number(e.target.value))}
            style={{
              background: 'transparent',
              color: '#fff',
              border: 'none',
              fontSize: '0.85rem',
              fontWeight: '500',
              cursor: 'pointer',
              outline: 'none'
            }}
          >
            {companies.length > 0 ? (
              companies.map((c) => (
                <option key={c.id} value={c.id} style={{ background: '#111827', color: '#fff' }}>
                  {c.name}
                </option>
              ))
            ) : (
              <option value="1" style={{ background: '#111827', color: '#fff' }}>ABC Traders</option>
            )}
          </select>
        </div>
      </div>

      <style>{`
        .nav-link {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem 0.9rem;
          color: #9ca3af;
          border-radius: 6px;
          font-size: 0.9rem;
          font-weight: 500;
          transition: all 0.15s ease;
        }
        .nav-link:hover {
          color: #fff;
          background: rgba(255, 255, 255, 0.05);
        }
        .nav-link.active {
          color: #fff;
          background: #1f2d42;
          font-weight: 600;
        }
      `}</style>
    </header>
  );
};
