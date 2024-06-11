import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Route, Routes, useNavigate } from 'react-router-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';
import Dashboard from './Dashboard';
import AccountView from './AccountView';
import Positions from './Positions';
import Trades from './Trades';
import Insights from './Insights';
import Sidebar from './Sidebar';
import Login from './Login';
import axios from 'axios';

const App = () => {
    const [token, setToken] = useState(localStorage.getItem('token'));

    useEffect(() => {
        if (token) {
            localStorage.setItem('token', token);
            axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
        } else {
            localStorage.removeItem('token');
            delete axios.defaults.headers.common['Authorization'];
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
