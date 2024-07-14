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
  Filler
} from 'chart.js';
import 'chartjs-adapter-moment';
import moment from 'moment-timezone';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import './Dashboard.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  TimeScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

const darkerPastelColors = [
  '#FF9AA2', '#FFB7B2', '#FFDAC1', '#E2F0CB', '#B5EAD7',
  '#C7CEEA', '#D3B8E6', '#B8D9E6', '#E6B8D2', '#B8E6C1',
  '#FFCCF9', '#CCCCFF', '#FFB3BA', '#FFDFBA', '#FFFFBA',
  '#BAFFC9', '#BAE1FF', '#FFD1DC', '#FFDAC1', '#FFF1BA',
  '#B6FFCE', '#FF9AA2', '#FFB7B2', '#FFDAC1', '#E2F0CB',
  '#FFBF86', '#FFC3A0', '#FFCCBB', '#D1C4E9', '#E0BBE4'
];

const Dashboard = () => {
  const [strategies, setStrategies] = useState([]);
  const [brokers, setBrokers] = useState([]);
  const [selectedStrategies, setSelectedStrategies] = useState([]);
  const [selectedBrokers, setSelectedBrokers] = useState([]);
  const [historicalValueData, setHistoricalValueData] = useState(null);
  const [totalFilteredValue, setTotalFilteredValue] = useState(0);
  const [loading, setLoading] = useState(true);
  const [initialData, setInitialData] = useState([]);
  const [startDate, setStartDate] = useState(moment().subtract(7, 'days').toDate());
  const [endDate, setEndDate] = useState(moment().add(1, 'days').toDate());

  const getColorForKey = (key, colors) => {
    if (!colors[key]) {
      const color = darkerPastelColors[Object.keys(colors).length % darkerPastelColors.length];
      colors[key] = { borderColor: color, backgroundColor: color };
    }
    return colors[key];
  };

  const getColorsFromStorage = (key) => {
    try {
      const storedColors = localStorage.getItem(key);
      return storedColors ? JSON.parse(storedColors) : {};
    } catch (error) {
      console.error('Error retrieving colors from local storage:', error);
      return {};
    }
  };

  const saveColorsToStorage = (key, colors) => {
    try {
      localStorage.setItem(key, JSON.stringify(colors));
    } catch (error) {
      console.error('Error saving colors to local storage:', error);
    }
  };

  const processHistoricalValues = useCallback((data) => {
    const colorKey = 'strategyColors';
    let colors = getColorsFromStorage(colorKey);
    let historicalData = {};
    let latestBalances = {};

    data.forEach(item => {
      let key = `${item.strategy} (${item.broker})`;
      if (!historicalData[key]) {
        historicalData[key] = [];
      }
      const { borderColor, backgroundColor } = getColorForKey(key, colors);
      historicalData[key].push({
        x: moment.utc(item.interval).tz(moment.tz.guess()).format(), // Convert UTC to local timezone
        y: item.total_balance,
        strategy: item.strategy,
        interval: item.interval
      });

      // Update latest balance for each strategy and broker
      if (!latestBalances[key] || moment(item.interval).isAfter(moment(latestBalances[key].interval))) {
        latestBalances[key] = {
          total_balance: item.total_balance,
          interval: item.interval
        };
      }
    });

    saveColorsToStorage(colorKey, colors);

    // Calculate total of latest balances
    const totalValue = Object.values(latestBalances).reduce((sum, item) => sum + item.total_balance, 0);
    setTotalFilteredValue(totalValue);

    let datasets = [];
    Object.keys(historicalData).forEach(key => {
      // Sort the data points by timestamp
      historicalData[key].sort((a, b) => new Date(a.x) - new Date(b.x));
      const { borderColor, backgroundColor } = colors[key];
      datasets.push({
        label: key,
        data: historicalData[key],
        fill: true,
        borderColor: borderColor,
        backgroundColor: backgroundColor,
        spanGaps: true,  // Connect data points even if there are gaps
        stack: 'stacked',
        pointRadius: 0  // Remove dots from lines
      });
    });

    return {
      datasets
    };
  }, []);

  const filterData = useCallback(() => {
    const filteredData = initialData.filter(item => 
      (selectedBrokers.length === 0 || selectedBrokers.includes(item.broker)) &&
      (selectedStrategies.length === 0 || selectedStrategies.includes(item.strategy)) &&
      (!startDate || new Date(item.interval) >= startDate) &&
      (!endDate || new Date(item.interval) <= endDate)
    );
    setHistoricalValueData(processHistoricalValues(filteredData));
  }, [initialData, selectedBrokers, selectedStrategies, startDate, endDate, processHistoricalValues]);

  const fetchHistoricalValues = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axiosInstance.get('/historic_balance_per_strategy');
      setInitialData(response.data.historic_balance_per_strategy);
      setHistoricalValueData(processHistoricalValues(response.data.historic_balance_per_strategy));
    } catch (error) {
      console.error('Error fetching historical values:', error);
    } finally {
      setLoading(false);
    }
  }, [processHistoricalValues]);

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
    if (initialData.length > 0) {
      filterData();
    }
  }, [initialData, selectedStrategies, selectedBrokers, startDate, endDate, filterData]);

  return (
    <div className="container-fluid dashboard">
      <div className="row mb-3">
        <div className="col-md-12 text-center">
          <div className="filtered-value-box">
            ${totalFilteredValue.toLocaleString()}
          </div>
        </div>
      </div>
      <div className="row mb-3">
        <div className="col-md-4">
          <Select
            isMulti
            options={strategies.map(strategy => ({ value: strategy, label: strategy }))}
            onChange={selectedOptions => setSelectedStrategies(selectedOptions.map(option => option.value))}
            placeholder="Select Strategies"
            className="basic-multi-select"
            classNamePrefix="select"
          />
        </div>
        <div className="col-md-4">
          <Select
            isMulti
            options={brokers.map(broker => ({ value: broker, label: broker }))}
            onChange={selectedOptions => setSelectedBrokers(selectedOptions.map(option => option.value))}
            placeholder="Select Brokers"
            className="basic-multi-select"
            classNamePrefix="select"
          />
        </div>
        <div className="col-md-2">
          <DatePicker
            selected={startDate}
            onChange={date => setStartDate(date)}
            selectsStart
            startDate={startDate}
            endDate={endDate}
            placeholderText="Start Date"
            className="form-control"
          />
        </div>
        <div className="col-md-2">
          <DatePicker
            selected={endDate}
            onChange={date => setEndDate(date)}
            selectsEnd
            startDate={startDate}
            endDate={endDate}
            placeholderText="End Date"
            className="form-control"
          />
        </div>
      </div>
      <div className="row">
        <div className="col-md-12">
          <div className="card shadow-sm">
            <div className="card-header bg-transparent border-0">
              <h5 className="mb-0">Historical Value per Strategy</h5>
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
                        },
                        stacked: true
                      },
                      y: {
                        beginAtZero: true,  // Ensure y-axis starts at 0
                        stacked: true
                      }
                    },
                    plugins: {
                      tooltip: {
                        callbacks: {
                          label: function(context) {
                            const { strategy, interval } = context.raw;
                            return `Strategy: ${strategy}<br>Time: ${moment(interval).format('MMM D, YYYY HH:mm')}<br>Balance: ${context.parsed.y.toLocaleString()}`;
                          },
                          labelTextColor: function() {
                            return '#4A90E2';  // Custom color for label text
                          }
                        },
                        itemSort: function(a, b) {
                          return b.parsed.y - a.parsed.y;
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
