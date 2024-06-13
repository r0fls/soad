import axios from 'axios';
import history from './history';

const baseURL = '$REACT_API_URL';

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

axiosInstance.interceptors.response.use(
  response => response,
  error => {
    if (error.response && error.response.status === 401) {
      history.push('/login');
    }
    return Promise.reject(error);
  }
);

export default axiosInstance;
export { history };
