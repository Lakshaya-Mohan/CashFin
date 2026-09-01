import { apiClient } from './client';

export const getCompanies = () => apiClient.get('/companies');
export const getCompany = (companyId) => apiClient.get(`/companies/${companyId}`);
