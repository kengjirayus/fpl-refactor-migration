import axios from 'axios';

const API_BASE_URL = 'http://127.0.0.1:8000/api'; // Update for production

const api = axios.create({
    baseURL: API_BASE_URL,
    headers: {
        'Content-Type': 'application/json',
    },
});

export const fplService = {
    getBootstrap: () => api.get('/bootstrap'),
    getFixtures: () => api.get('/fixtures'),
    analyzeTeam: (teamId) => api.get(`/analyze/${teamId}`),
    simulateTeam: (data) => api.post('/simulate', data),
    getTransferSuggestions: (data) => api.post('/transfers/suggest', data),
    getSettings: (teamId) => api.get(`/settings/${teamId}`),
    saveSettings: (data) => api.post('/settings', data),
    getGeneralData: () => api.get('/general-data'),
};

export default api;
