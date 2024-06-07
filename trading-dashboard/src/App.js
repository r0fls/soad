import React from 'react';
import { BrowserRouter as Router, Route, Routes } from 'react-router-dom';
import 'bootstrap/dist/css/bootstrap.min.css';
import './App.css';
import Dashboard from './Dashboard';
import AccountView from './AccountView';
import Positions from './Positions';
import Trades from './Trades';
import Insights from './Insights';
import Sidebar from './Sidebar';

const App = () => {
  return (
    <Router>
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
    </Router>
  );
};

export default App;
