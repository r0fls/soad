import React, { useState, useEffect } from 'react';
import axiosInstance from './axiosInstance';
import 'bootstrap/dist/css/bootstrap.min.css';

const AdjustBalance = () => {
  const [brokersStrategies, setBrokersStrategies] = useState([]);
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
      const dataWithNewBalance = response.data.map(item => ({
        ...item,
        new_total_balance: item.total_balance
      }));
      setBrokersStrategies(dataWithNewBalance);
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
      fetchBrokersStrategies();  // Refresh the balances after adjustment
    } catch (error) {
      console.error('Error adjusting balance:', error);
      setResponseMessage('Error adjusting balance: ' + error.message);
    }
  };

  const handleDeleteStrategy = async (broker, strategy) => {
    if (window.confirm(`Are you sure you want to delete the strategy "${strategy}" for broker "${broker}"?`)) {
      try {
        const response = await axiosInstance.post('/delete_strategy', {
          broker,
          strategy_name: strategy
        }, {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + localStorage.getItem('jwt_token')
          }
        });
        setResponseMessage(JSON.stringify(response.data));
        fetchBrokersStrategies();  // Refresh after deletion
      } catch (error) {
        console.error('Error deleting strategy:', error);
        setResponseMessage('Error deleting strategy: ' + error.message);
      }
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
            <th>Balance</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {brokersStrategies.map((item, index) => (
            <tr key={index}>
              <td>{item.broker}</td>
              <td>{item.strategy}</td>
              <td>
                {/* Disable input for "uncategorized" strategies */}
                {item.strategy.toLowerCase() === 'uncategorized' ? (
                  <span>{item.total_balance}</span>
                ) : (
                  <input
                    type="number"
                    className="form-control"
                    value={item.new_total_balance || ''}
                    onChange={(e) => {
                      const newBrokersStrategies = brokersStrategies.map((el, idx) => (
                        idx === index ? { ...el, new_total_balance: e.target.value } : el
                      ));
                      setBrokersStrategies(newBrokersStrategies);
                    }}
                    required
                  />
                )}
              </td>
              <td>
                {/* Show the Adjust Balance button only for non-uncategorized strategies */}
                {item.strategy.toLowerCase() !== 'uncategorized' && (
                  <>
                    <button
                      className="btn btn-primary"
                      onClick={() => handleAdjustBalance(item.broker, item.strategy, item.new_total_balance)}
                      disabled={!item.new_total_balance}
                    >
                      Adjust Balance
                    </button>
                    {/* Show delete button only for non-uncategorized strategies */}
                    <button
                      className="btn btn-danger ml-2"
                      onClick={() => handleDeleteStrategy(item.broker, item.strategy)}
                    >
                      &#10060; Delete
                    </button>
                  </>
                )}
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
