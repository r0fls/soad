import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, Navigate } from 'react-router-dom';
import axiosInstance from './axiosInstance';
import Sidebar from './Sidebar';
import Dashboard from './Dashboard';
import AccountView from './AccountView';
import Positions from './Positions';
import Trades from './Trades';
import Insights from './Insights';
import Login from './Login';

const App = () => {
  const [token, setToken] = useState(localStorage.getItem('token'));

  useEffect(() => {
    if (token) {
      localStorage.setItem('token', token);
      axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${token}`;
    } else {
      localStorage.removeItem('token');
      delete axiosInstance.defaults.headers.common['Authorization'];
    }
  }, [token]);

  return (
    <Router>
      {token ? (
        <>
          <Sidebar />
          <div className="container-fluid">
            <Routes>
              <Route exact path="/" element={<Dashboard />} />
              <Route path="/accounts" element={<AccountView />} />
              <Route path="/positions" element={<Positions />} />
              <Route path="/trades" element={<Trades />} />
              <Route path="/insights" element={<Insights />} />
              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          </div>
        </>
      ) : (
        <Routes>
          <Route path="*" element={<Login setToken={setToken} />} />
        </Routes>
      )}
    </Router>
  );
};

export default App;
