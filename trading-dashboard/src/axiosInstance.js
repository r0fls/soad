import axios from 'axios';

const baseURL = process.env.REACT_API_URL || 'http://localhost:8000';

const axiosInstance = axios.create({
    baseURL: baseURL,
});

export default axiosInstance;
