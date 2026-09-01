import React, { useState } from 'react';
import {
  importBankCsv,
  importInvoicesJson,
  importExpensesJson,
  importReceiptImage,
} from '../api/ingestion';
import { UploadCloud, FileText, FileCode, Image as ImageIcon, CheckCircle2, AlertCircle } from 'lucide-react';

export const Ingestion = ({ companyId }) => {
  const [activeTab, setActiveTab] = useState('csv');
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [accountId, setAccountId] = useState(1);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
      setResult(null);
      setError(null);
    }
  };

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select a file to upload.');
      return;
    }

    setUploading(true);
    setResult(null);
    setError(null);

    try {
      let res = null;
      if (activeTab === 'csv') {
        res = await importBankCsv(companyId, accountId, selectedFile);
      } else if (activeTab === 'invoices') {
        res = await importInvoicesJson(companyId, selectedFile);
      } else if (activeTab === 'expenses') {
        res = await importExpensesJson(companyId, selectedFile, accountId);
      } else if (activeTab === 'receipts') {
        res = await importReceiptImage(companyId, accountId, selectedFile);
      }

      setResult(res);
      setSelectedFile(null);
    } catch (err) {
      setError(err.message || 'Ingestion failed. Please check the file format.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
      <div className="page-header" style={{ marginBottom: 0 }}>
        <div>
          <h1 className="page-title">Data Ingestion Center</h1>
          <p className="page-subtitle">Import bank statements, invoices, expenses, and receipt images with duplicate detection</p>
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: '0.75rem', borderBottom: '1px solid #1f2d42', paddingBottom: '0.75rem' }}>
        <button
          className={`btn ${activeTab === 'csv' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => { setActiveTab('csv'); setResult(null); setError(null); }}
        >
          <FileText size={18} />
          <span>Bank Statement (CSV)</span>
        </button>

        <button
          className={`btn ${activeTab === 'invoices' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => { setActiveTab('invoices'); setResult(null); setError(null); }}
        >
          <FileCode size={18} />
          <span>Customer Invoices (JSON)</span>
        </button>

        <button
          className={`btn ${activeTab === 'expenses' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => { setActiveTab('expenses'); setResult(null); setError(null); }}
        >
          <FileCode size={18} />
          <span>Vendor Expenses (JSON)</span>
        </button>

        <button
          className={`btn ${activeTab === 'receipts' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => { setActiveTab('receipts'); setResult(null); setError(null); }}
        >
          <ImageIcon size={18} />
          <span>Receipt Image (OCR)</span>
        </button>
      </div>

      {/* Upload Zone Card */}
      <div className="card">
        <h2 className="card-title">
          {activeTab === 'csv' && 'Upload Bank Statement CSV'}
          {activeTab === 'invoices' && 'Upload Customer Invoices JSON'}
          {activeTab === 'expenses' && 'Upload Vendor Expenses JSON'}
          {activeTab === 'receipts' && 'Upload Receipt Image (JPG/PNG)'}
        </h2>

        <form onSubmit={handleUpload}>
          {(activeTab === 'csv' || activeTab === 'receipts' || activeTab === 'expenses') && (
            <div className="form-group" style={{ maxWidth: '300px' }}>
              <label className="form-label">Account ID</label>
              <input
                type="number"
                value={accountId}
                onChange={(e) => setAccountId(Number(e.target.value))}
                className="form-control"
              />
            </div>
          )}

          <div
            className="file-upload-zone"
            onClick={() => document.getElementById('file-input').click()}
            style={{ marginBottom: '1.25rem' }}
          >
            <UploadCloud size={40} style={{ color: '#38bdf8', marginBottom: '0.75rem' }} />
            <div style={{ fontWeight: '600', color: '#fff', fontSize: '1rem' }}>
              {selectedFile ? selectedFile.name : 'Click to select or drag file here'}
            </div>
            <div style={{ fontSize: '0.8rem', color: '#9ca3af', marginTop: '0.35rem' }}>
              {activeTab === 'csv' && 'Accepted format: .csv'}
              {(activeTab === 'invoices' || activeTab === 'expenses') && 'Accepted format: .json'}
              {activeTab === 'receipts' && 'Accepted formats: .jpg, .jpeg, .png'}
            </div>
            <input
              id="file-input"
              type="file"
              onChange={handleFileChange}
              accept={
                activeTab === 'csv'
                  ? '.csv'
                  : activeTab === 'receipts'
                  ? '.jpg,.jpeg,.png'
                  : '.json'
              }
              style={{ display: 'none' }}
            />
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button type="submit" className="btn btn-primary" disabled={uploading || !selectedFile}>
              {uploading ? 'Processing Ingestion...' : 'Start Upload & Process'}
            </button>
          </div>
        </form>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="error-banner">
          <AlertCircle size={20} />
          <span>{error}</span>
        </div>
      )}

      {/* Ingestion Result Summary */}
      {result && (
        <div className="card" style={{ borderLeft: '4px solid #10b981' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.25rem' }}>
            <CheckCircle2 size={24} style={{ color: '#10b981' }} />
            <div>
              <h3 style={{ fontSize: '1.2rem', fontWeight: '700', color: '#fff' }}>
                Ingestion Completed Successfully
              </h3>
              <p style={{ fontSize: '0.85rem', color: '#9ca3af' }}>
                File parsed, normalized, validated, and checked for duplicates.
              </p>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))', gap: '1rem', background: '#0d131f', padding: '1rem', borderRadius: '8px' }}>
            <div>
              <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>TOTAL RECORDS</span>
              <div style={{ fontSize: '1.25rem', fontWeight: '700', color: '#fff' }}>{result.total_records}</div>
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>INSERTED</span>
              <div style={{ fontSize: '1.25rem', fontWeight: '700', color: '#10b981' }}>{result.inserted_records}</div>
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>EXACT DUPLICATES</span>
              <div style={{ fontSize: '1.25rem', fontWeight: '700', color: '#f59e0b' }}>{result.duplicate_records}</div>
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>POSSIBLE DUPLICATES</span>
              <div style={{ fontSize: '1.25rem', fontWeight: '700', color: '#3b82f6' }}>{result.possible_duplicates}</div>
            </div>
            <div>
              <span style={{ fontSize: '0.75rem', color: '#9ca3af' }}>FAILED / ERRORS</span>
              <div style={{ fontSize: '1.25rem', fontWeight: '700', color: result.failed_records > 0 ? '#ef4444' : '#9ca3af' }}>
                {result.failed_records}
              </div>
            </div>
          </div>

          {/* Validation Errors List if any */}
          {result.errors && result.errors.length > 0 && (
            <div style={{ marginTop: '1.25rem' }}>
              <h4 style={{ fontSize: '0.95rem', fontWeight: '600', color: '#f87171', marginBottom: '0.5rem' }}>
                Validation / Parsing Messages
              </h4>
              <ul style={{ paddingLeft: '1.25rem', color: '#9ca3af', fontSize: '0.85rem' }}>
                {result.errors.map((e, idx) => (
                  <li key={idx}>
                    Row {e.row_number} [{e.field}]: {e.error_message}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
