import { apiClient } from './client';

export const getCashFlowProjection = (companyId, params = {}) =>
  apiClient.get(`/companies/${companyId}/cash-flow`, { params });
