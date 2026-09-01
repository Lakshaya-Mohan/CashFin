import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { getCompanies } from './api/companies';
import { Navbar } from './components/Navbar';
import { Dashboard } from './pages/Dashboard';
import { Forecast } from './pages/Forecast';
import { Decisions } from './pages/Decisions';
import { Ingestion } from './pages/Ingestion';

export default function App() {
  const [companies, setCompanies] = useState([]);
  const [selectedCompanyId, setSelectedCompanyId] = useState(1);

  useEffect(() => {
    getCompanies()
      .then((res) => {
        if (res && res.length > 0) {
          setCompanies(res);
          setSelectedCompanyId(res[0].id);
        }
      })
      .catch(() => {
        // Fallback default
        setCompanies([{ id: 1, name: 'ABC Traders' }]);
        setSelectedCompanyId(1);
      });
  }, []);

  return (
    <Router>
      <div className="app-container">
        <Navbar
          companies={companies}
          selectedCompanyId={selectedCompanyId}
          onSelectCompany={(id) => setSelectedCompanyId(id)}
        />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard companyId={selectedCompanyId} />} />
            <Route path="/dashboard" element={<Navigate to="/" replace />} />
            <Route path="/forecast" element={<Forecast companyId={selectedCompanyId} />} />
            <Route path="/decisions" element={<Decisions companyId={selectedCompanyId} />} />
            <Route path="/ingestion" element={<Ingestion companyId={selectedCompanyId} />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}
