import axios from 'axios';
import history from './history';

const baseURL = process.env.REACT_APP_API_URL || '$REACT_API_URL';

const axiosInstance = axios.create({
  baseURL: baseURL,
});

export const isTokenExpired = (token) => {
  if (!token) return true;

  const payload = JSON.parse(atob(token.split('.')[1]));
  const currentTime = Date.now() / 1000;

  return payload.exp < currentTime;
};

axiosInstance.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    if (isTokenExpired(token)) {
      history.push('/login');
      localStorage.removeItem('token');
      throw new axios.Cancel('JWT token expired');
    }
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
