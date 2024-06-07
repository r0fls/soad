import React, { useEffect, useState, useCallback } from 'react';
import axiosInstance from './axiosInstance';
import { Bar, Doughnut } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Tooltip,
  Legend,
} from 'chart.js';
import 'chartjs-adapter-moment';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Tooltip,
  Legend
);

const AccountView = () => {
  const [accountValuesData, setAccountValuesData] = useState(null);
  const [tradesPerStrategyData, setTradesPerStrategyData] = useState(null);
  const [tradeSuccessRateData, setTradeSuccessRateData] = useState(null);

  const processAccountValues = useCallback((data) => {
    let brokers = [];
    let values = [];
    let totalValue = 0;

    Object.keys(data.account_values).forEach(broker => {
      brokers.push(broker);
      let value = data.account_values[broker];
      values.push(value);
      totalValue += value;
    });

    return {
      chartData: {
        labels: brokers,
        datasets: [{
          label: 'Account Value',
          data: values,
          backgroundColor: [
            'rgba(255, 99, 132, 0.2)',
            'rgba(54, 162, 235, 0.2)',
            'rgba(255, 206, 86, 0.2)'
          ],
          borderColor: [
            'rgba(255, 99, 132, 1)',
            'rgba(54, 162, 235, 1)',
            'rgba(255, 206, 86, 1)'
          ],
          borderWidth: 1
        }]
      },
      tableData: brokers.map((broker, index) => ({
        broker,
        value: values[index].toFixed(2)
      })),
      totalValue: totalValue.toFixed(2)
    };
  }, []);

  const processTradesPerStrategy = useCallback((data) => {
    let strategies = [];
    let counts = [];

    data.trades_per_strategy.forEach(item => {
      strategies.push(`${item.strategy} (${item.broker})`);
      counts.push(item.count);
    });

    return {
      labels: strategies,
      datasets: [{
        label: 'Number of Trades',
        data: counts,
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        borderColor: 'rgba(75, 192, 192, 1)',
        borderWidth: 1
      }]
    };
  }, []);

  const processTradeSuccessRate = useCallback((data) => {
    let strategies = [];
    let successRates = [];

    data.trade_success_rate.forEach(item => {
      strategies.push(`${item.strategy} (${item.broker})`);
      let successRate = (item.successful_trades / item.total_trades) * 100;
      successRates.push(successRate);
    });

    return {
      labels: strategies,
      datasets: [{
        label: 'Success Rate (%)',
        data: successRates,
        backgroundColor: 'rgba(153, 102, 255, 0.2)',
        borderColor: 'rgba(153, 102, 255, 1)',
        borderWidth: 1
      }]
    };
  }, []);

  const updateCharts = useCallback(async () => {
    try {
      const accountValues = await axiosInstance.get('/account_values');
      const tradesPerStrategy = await axiosInstance.get('/trades_per_strategy');
      const tradeSuccessRate = await axiosInstance.get('/trade_success_rate');

      setAccountValuesData(processAccountValues(accountValues.data));
      setTradesPerStrategyData(processTradesPerStrategy(tradesPerStrategy.data));
      setTradeSuccessRateData(processTradeSuccessRate(tradeSuccessRate.data));
    } catch (error) {
      console.error('Error updating charts:', error);
    }
  }, [processAccountValues, processTradesPerStrategy, processTradeSuccessRate]);

  useEffect(() => {
    updateCharts();
  }, [updateCharts]);

  return (
    <div className="container-fluid">
      <div className="row">
        <div className="col-md-8">
          <div className="card">
            <div className="card-header">
              Account Values
            </div>
            <div className="card-body">
              {accountValuesData && <Doughnut data={accountValuesData.chartData} />}
              <table className="table">
                <thead>
                  <tr>
                    <th>Broker</th>
                    <th>Account Value</th>
                  </tr>
                </thead>
                <tbody>
                  {accountValuesData && accountValuesData.tableData.map((item, index) => (
                    <tr key={index}>
                      <td>{item.broker}</td>
                      <td>{item.value}</td>
                    </tr>
                  ))}
                </tbody>
                <tfoot>
                  <tr>
                    <th>Total</th>
                    <th>{accountValuesData ? accountValuesData.totalValue : ''}</th>
                  </tr>
                </tfoot>
              </table>
            </div>
          </div>
        </div>
        <div className="col-md-4">
          <div className="card">
            <div className="card-header">
              Number of Trades per Strategy
            </div>
            <div className="card-body">
              {tradesPerStrategyData && <Bar data={tradesPerStrategyData} />}
            </div>
          </div>
          <div className="card">
            <div className="card-header">
              Trade Success Rate
            </div>
            <div className="card-body">
              {tradeSuccessRateData && <Bar data={tradeSuccessRateData} />}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AccountView;
