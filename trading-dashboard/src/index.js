import React, { useEffect } from 'react';
import ReactDOM from 'react-dom/client';
import { RouterProvider } from 'react-router-dom';
import router from './routes';
import './index.css';
import 'bootstrap/dist/css/bootstrap.min.css';
import reportWebVitals from './reportWebVitals';
import Sidebar from './Sidebar';
import { isTokenExpired } from './axiosInstance';
import history from './history';

// Function to check token expiration and redirect if necessary
const checkTokenExpiration = () => {
  const token = localStorage.getItem('token');
  if (isTokenExpired(token)) {
    localStorage.removeItem('token');
    history.push('/login');
  }
};

const App = () => {
  useEffect(() => {
    checkTokenExpiration();
  }, []);

  return (
    <>
      <RouterProvider router={router}>
        <Sidebar />
      </RouterProvider>
    </>
  );
};

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

reportWebVitals();
