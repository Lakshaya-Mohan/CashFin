import { apiClient } from './client';

export const getForecast = (companyId, params = {}) =>
  apiClient.get(`/companies/${companyId}/forecast`, { params });
