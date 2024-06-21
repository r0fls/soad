import React, { useState, useEffect } from 'react';
import axiosInstance from './axiosInstance';
import 'bootstrap/dist/css/bootstrap.min.css';

const AdjustBalance = () => {
  const [brokersStrategies, setBrokersStrategies] = useState([]);
  const [selectedBroker, setSelectedBroker] = useState('');
  const [selectedStrategy, setSelectedStrategy] = useState('');
  const [newTotalBalance, setNewTotalBalance] = useState('');
  const [responseMessage, setResponseMessage] = useState('');

  useEffect(() => {
    fetchBrokersStrategies();
  }, []);

  const fetchBrokersStrategies = async () => {
    try {
      const response = await axiosInstance.get('/get_brokers_strategies', {
        headers: {
          'Authorization': 'Bearer ' + localStorage.getItem('jwt_token')
        }
      });
      setBrokersStrategies(response.data);
    } catch (error) {
      console.error('Error fetching brokers strategies:', error);
      setResponseMessage('Error fetching brokers strategies: ' + error.message);
    }
  };

  const handleAdjustBalance = async (broker, strategy, amount) => {
    try {
      const response = await axiosInstance.post('/adjust_balance', {
        broker,
        strategy_name: strategy,
        new_total_balance: parseFloat(amount)
      }, {
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + localStorage.getItem('jwt_token')
        }
      });
      setResponseMessage(JSON.stringify(response.data));
    } catch (error) {
      console.error('Error adjusting balance:', error);
      setResponseMessage('Error adjusting balance: ' + error.message);
    }
  };

  return (
    <div className="container">
      <h1 className="my-4">Adjust Strategy Balance</h1>
      <table className="table table-striped">
        <thead>
          <tr>
            <th>Broker</th>
            <th>Strategy</th>
            <th>New Total Balance</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {brokersStrategies.map((item, index) => (
            <tr key={index}>
              <td>{item.broker}</td>
              <td>{item.strategy}</td>
              <td>
                <input
                  type="number"
                  className="form-control"
                  value={selectedBroker === item.broker && selectedStrategy === item.strategy ? newTotalBalance : ''}
                  onChange={(e) => {
                    setSelectedBroker(item.broker);
                    setSelectedStrategy(item.strategy);
                    setNewTotalBalance(e.target.value);
                  }}
                  required
                />
              </td>
              <td>
                <button
                  className="btn btn-primary"
                  onClick={() => handleAdjustBalance(item.broker, item.strategy, newTotalBalance)}
                  disabled={selectedBroker !== item.broker || selectedStrategy !== item.strategy || !newTotalBalance}
                >
                  Adjust Balance
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div id="response" className="alert alert-info mt-4">{responseMessage}</div>
    </div>
  );
};

export default AdjustBalance;
