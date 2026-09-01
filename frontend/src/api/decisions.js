import { apiClient } from './client';

export const evaluateDecision = (companyId, payload = {}) =>
  apiClient.post(`/companies/${companyId}/decision`, payload);
