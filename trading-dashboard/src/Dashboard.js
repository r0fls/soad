import React, { useEffect, useState, useCallback } from 'react';
import axiosInstance from './axiosInstance';
import Select from 'react-select';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  TimeScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import 'chartjs-adapter-moment';

ChartJS.register(
  CategoryScale,
  LinearScale,
  TimeScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const Dashboard = () => {
  const [strategies, setStrategies] = useState([]);
  const [brokers, setBrokers] = useState([]);
  const [selectedStrategies, setSelectedStrategies] = useState([]);
  const [selectedBrokers, setSelectedBrokers] = useState([]);
  const [historicalValueData, setHistoricalValueData] = useState(null);

  const loadFilters = async () => {
    try {
      const response = await axiosInstance.get('/trades_per_strategy');
      const strategies = new Set();
      const brokers = new Set();

      response.data.trades_per_strategy.forEach(item => {
        strategies.add(item.strategy);
        brokers.add(item.broker);
      });

      setStrategies([...strategies]);
      setBrokers([...brokers]);
    } catch (error) {
      console.error('Error loading filters:', error);
    }
  };

  const processHistoricalValues = useCallback((data) => {
    let historicalData = {};

    data.historic_balance_per_strategy.forEach(item => {
      if ((!selectedStrategies.length || selectedStrategies.includes(item.strategy)) &&
          (!selectedBrokers.length || selectedBrokers.includes(item.broker))) {
        let key = `${item.strategy} (${item.broker})`;
        if (!historicalData[key]) {
          historicalData[key] = [];
        }
        historicalData[key].push({
          x: item.hour,
          y: item.total_balance
        });
      }
    });

    let datasets = [];
    Object.keys(historicalData).forEach(key => {
      datasets.push({
        label: key,
        data: historicalData[key],
        fill: false,
        borderColor: 'rgba(75, 192, 192, 1)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
      });
    });

    return {
      datasets
    };
  }, [selectedStrategies, selectedBrokers]);

  const updateCharts = useCallback(async () => {
    try {
      const historicalValues = await axiosInstance.get('/historic_balance_per_strategy');
      setHistoricalValueData(processHistoricalValues(historicalValues.data));
    } catch (error) {
      console.error('Error updating charts:', error);
    }
  }, [processHistoricalValues]);

  useEffect(() => {
    loadFilters();
    updateCharts();
  }, [updateCharts]);

  useEffect(() => {
    updateCharts();
  }, [selectedStrategies, selectedBrokers, updateCharts]);

  return (
    <div className="container-fluid">
      <div className="row filter-bar">
        <div className="col-md-6">
          <Select
            isMulti
            options={strategies.map(strategy => ({ value: strategy, label: strategy }))}
            onChange={selectedOptions => setSelectedStrategies(selectedOptions.map(option => option.value))}
          />
        </div>
        <div className="col-md-6">
          <Select
            isMulti
            options={brokers.map(broker => ({ value: broker, label: broker }))}
            onChange={selectedOptions => setSelectedBrokers(selectedOptions.map(option => option.value))}
          />
        </div>
      </div>
      <div className="row">
        <div className="col-md-12">
          <div className="card">
            <div className="card-header">
              Historical Value per Strategy
            </div>
            <div className="card-body">
              {historicalValueData && <Line data={historicalValueData} options={{ scales: { x: { type: 'time', time: { unit: 'hour' }}}}} />}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
