import { apiClient } from './client';

export const getFinancialState = (companyId, params = {}) =>
  apiClient.get(`/companies/${companyId}/financial-state`, { params });
