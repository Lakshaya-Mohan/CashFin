import { apiClient } from './client';

export const importBankCsv = (companyId, accountId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient.post(`/companies/${companyId}/accounts/${accountId}/transactions/import`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};

export const importInvoicesJson = (companyId, payload) => {
  if (payload instanceof File) {
    const formData = new FormData();
    formData.append('file', payload);
    return apiClient.post(`/companies/${companyId}/invoices/import`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }
  return apiClient.post(`/companies/${companyId}/invoices/import`, payload);
};

export const importExpensesJson = (companyId, payload, accountId = null) => {
  const params = accountId ? { account_id: accountId } : {};
  if (payload instanceof File) {
    const formData = new FormData();
    formData.append('file', payload);
    return apiClient.post(`/companies/${companyId}/expenses/import`, formData, {
      params,
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  }
  return apiClient.post(`/companies/${companyId}/expenses/import`, payload, { params });
};

export const importReceiptImage = (companyId, accountId, file) => {
  const formData = new FormData();
  formData.append('file', file);
  return apiClient.post(`/companies/${companyId}/accounts/${accountId}/receipts`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
};
