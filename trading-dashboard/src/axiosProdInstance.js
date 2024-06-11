import axios from 'axios';

// Hardcode this for now since I can't get the build working
const baseURL = 'http://system-of-a-dow-api:8000';

const axiosInstance = axios.create({
    baseURL: baseURL,
});

export default axiosInstance;
