import axios from 'axios';

const baseURL = process.env.REACT_API_URL || 'http://localhost:8000';

const axiosInstance = axios.create({
    baseURL: baseURL,
});

axiosInstance.interceptors.request.use((config) => {
    const token = localStorage.getItem('token');
    if (token) {
        config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
});

export default axiosInstance;
