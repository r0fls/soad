import React, { useEffect, useState, useCallback } from 'react';
import axiosInstance from './axiosInstance';
import { Spinner } from 'react-bootstrap';
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
import moment from 'moment-timezone';

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
  const [loading, setLoading] = useState(true);

  const processHistoricalValues = useCallback((data) => {
    let historicalData = {};

    data.historic_balance_per_strategy.forEach(item => {
      let key = `${item.strategy} (${item.broker})`;
      if (!historicalData[key]) {
        historicalData[key] = [];
      }
      historicalData[key].push({
        x: moment.utc(item.interval).tz(moment.tz.guess()).format(), // Convert UTC to local timezone
        y: item.total_balance
      });
    });

    let datasets = [];
    Object.keys(historicalData).forEach(key => {
      // Sort the data points by timestamp
      historicalData[key].sort((a, b) => new Date(a.x) - new Date(b.x));
      datasets.push({
        label: key,
        data: historicalData[key],
        fill: false,
        borderColor: 'rgba(75, 192, 192, 1)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        spanGaps: true  // Connect data points even if there are gaps
      });
    });

    return {
      datasets
    };
  }, []);

  const fetchHistoricalValues = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axiosInstance.get('/historic_balance_per_strategy', {
        params: { brokers: selectedBrokers, strategies: selectedStrategies }
      });
      setHistoricalValueData(processHistoricalValues(response.data));
    } catch (error) {
      console.error('Error fetching historical values:', error);
    } finally {
      setLoading(false);
    }
  }, [selectedBrokers, selectedStrategies, processHistoricalValues]);

  const populateFilters = useCallback(async () => {
    try {
      const response = await axiosInstance.get('/trades_per_strategy');
      const strategiesSet = new Set();
      const brokersSet = new Set();

      response.data.trades_per_strategy.forEach(item => {
        strategiesSet.add(item.strategy);
        brokersSet.add(item.broker);
      });

      setStrategies([...strategiesSet]);
      setBrokers([...brokersSet]);
    } catch (error) {
      console.error('Error populating filters:', error);
    }
  }, []);

  useEffect(() => {
    populateFilters();
    fetchHistoricalValues();
  }, [populateFilters, fetchHistoricalValues]);

  useEffect(() => {
    fetchHistoricalValues();
  }, [selectedStrategies, selectedBrokers, fetchHistoricalValues]);

  return (
    <div className="container-fluid">
      <div className="row mb-3">
        <div className="col-md-6">
          <Select
            isMulti
            options={strategies.map(strategy => ({ value: strategy, label: strategy }))}
            onChange={selectedOptions => setSelectedStrategies(selectedOptions.map(option => option.value))}
            placeholder="Select Strategies"
            className="basic-multi-select"
            classNamePrefix="select"
          />
        </div>
        <div className="col-md-6">
          <Select
            isMulti
            options={brokers.map(broker => ({ value: broker, label: broker }))}
            onChange={selectedOptions => setSelectedBrokers(selectedOptions.map(option => option.value))}
            placeholder="Select Brokers"
            className="basic-multi-select"
            classNamePrefix="select"
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
              {loading ? (
                <div className="text-center my-5">
                  <Spinner animation="border" role="status">
                    <span className="visually-hidden">Loading...</span>
                  </Spinner>
                </div>
              ) : (
                historicalValueData && <Line
                  data={historicalValueData}
                  options={{
                    scales: {
                      x: {
                        type: 'time',
                        time: {
                          unit: 'day', // Display unit by day
                          tooltipFormat: 'll', // Format for tooltip
                          displayFormats: {
                            day: 'MMM D, YYYY' // Format for display
                          }
                        },
                        adapters: {
                          date: {
                            zone: moment.tz.guess()  // Use local timezone
                          }
                        }
                      }
                    },
                    plugins: {
                      tooltip: {
                        callbacks: {
                          label: function(context) {
                            return context.parsed.y !== null ? context.parsed.y.toLocaleString() : '';
                          }
                        }
                      }
                    }
                  }}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
