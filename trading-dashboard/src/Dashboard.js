import React, { useEffect, useState, useCallback } from 'react';
import axiosInstance from './axiosInstance';
import { Spinner } from 'react-bootstrap';
import Select from 'react-select';
import { Line, Pie } from 'react-chartjs-2';
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
  Filler,
  ArcElement,
} from 'chart.js';
import 'chartjs-adapter-moment';
import moment from 'moment-timezone';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  TimeScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
  ArcElement
);

const Dashboard = () => {
  const [strategies, setStrategies] = useState([]);
  const [brokers, setBrokers] = useState([]);
  const [selectedStrategies, setSelectedStrategies] = useState([]);
  const [selectedBrokers, setSelectedBrokers] = useState([]);
  const [historicalValueData, setHistoricalValueData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [initialData, setInitialData] = useState([]);
  const [startDate, setStartDate] = useState(moment().subtract(7, 'days').toDate());
  const [endDate, setEndDate] = useState(moment().add(1, 'days').toDate());
  const [breakdownData, setBreakdownData] = useState(null);

  const processHistoricalValues = useCallback((data) => {
    let historicalData = {};

    data.forEach(item => {
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
        fill: true,
        borderColor: 'rgba(75, 192, 192, 1)',
        backgroundColor: 'rgba(75, 192, 192, 0.2)',
        spanGaps: true,  // Connect data points even if there are gaps
        stack: 'stacked'
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

  const fetchBreakdownData = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axiosInstance.get('/breakdown');
      const { stocks, options, cash_balances } = response.data;

      const cashValue = cash_balances.reduce((acc, balance) => acc + balance.balance, 0);
      const stockValue = stocks.reduce((acc, stock) => acc + (stock.latest_price * stock.quantity), 0);
      const optionValue = options.reduce((acc, option) => acc + (option.latest_price * option.quantity), 0);

      setBreakdownData({
        labels: ['Cash', 'Stocks', 'Options'],
        datasets: [{
          data: [cashValue, stockValue, optionValue],
          backgroundColor: ['#FF6384', '#36A2EB', '#FFCE56'],
        }]
      });
    } catch (error) {
      console.error('Error fetching breakdown data:', error);
    } finally {
      setLoading(false);
    }
  }, []);

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
    fetchBreakdownData();
  }, [populateFilters, fetchHistoricalValues, fetchBreakdownData]);

  useEffect(() => {
    if (initialData.length > 0) {
      filterData();
    }
  }, [selectedStrategies, selectedBrokers, startDate, endDate, filterData]);

  return (
    <div className="container-fluid">
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
                        },
                        stacked: true
                      },
                      y: {
                        stacked: true
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
      <div className="row mt-5">
        <div className="col-md-12">
          <div className="card">
            <div className="card-header">
              Breakdown of Values
            </div>
            <div className="card-body">
              {loading ? (
                <div className="text-center my-5">
                  <Spinner animation="border" role="status">
                    <span className="visually-hidden">Loading...</span>
                  </Spinner>
                </div>
              ) : (
                breakdownData && <Pie data={breakdownData} />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
