import React, { useState, useEffect } from 'react';

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
    const response = await fetch('/get_brokers_strategies', {
      method: 'GET',
      headers: {
        'Authorization': 'Bearer ' + localStorage.getItem('jwt_token')
      }
    });
    const result = await response.json();
    setBrokersStrategies(result);
  };

  const handleAdjustBalance = async (broker, strategy, amount) => {
    const response = await fetch('/adjust_balance', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + localStorage.getItem('jwt_token')
      },
      body: JSON.stringify({ broker, strategy_name: strategy, new_total_balance: parseFloat(amount) })
    });
    const result = await response.json();
    setResponseMessage(JSON.stringify(result));
  };

  return (
    <div>
      <h1>Adjust Strategy Balance</h1>
      <table>
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
      <div id="response">{responseMessage}</div>
    </div>
  );
};

export default AdjustBalance;
