import React, { useEffect, useState, useCallback } from 'react';
import axiosInstance from './axiosInstance';
import Select from 'react-select';
import { Spinner, Table, Card, Row, Col } from 'react-bootstrap';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import './Trades.css'; // Assuming you have a CSS file for custom styles

const Trades = () => {
  const [brokers, setBrokers] = useState([]);
  const [strategies, setStrategies] = useState([]);
  const [selectedBrokers, setSelectedBrokers] = useState([]);
  const [selectedStrategies, setSelectedStrategies] = useState([]);
  const [selectedOrderTypes, setSelectedOrderTypes] = useState([]);
  const [startDate, setStartDate] = useState(null);
  const [endDate, setEndDate] = useState(null);
  const [trades, setTrades] = useState([]);
  const [initialTrades, setInitialTrades] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const filterTrades = useCallback(() => {
    const filteredTrades = initialTrades.filter(trade =>
      (selectedBrokers.length === 0 || selectedBrokers.includes(trade.broker)) &&
      (selectedStrategies.length === 0 || selectedStrategies.includes(trade.strategy)) &&
      (selectedOrderTypes.length === 0 || selectedOrderTypes.includes(trade.side)) &&
      (!startDate || new Date(trade.timestamp) >= startDate) &&
      (!endDate || new Date(trade.timestamp) <= endDate)
    );
    setTrades(filteredTrades);
  }, [initialTrades, selectedBrokers, selectedStrategies, selectedOrderTypes, startDate, endDate]);

  const calculateStats = useCallback((filteredTrades) => {
    if (filteredTrades.length === 0) return null;

    const filteredSellTrades = filteredTrades.filter(trade => trade.side === 'sell');
    const hasSellTrades = filteredSellTrades.length > 0;

    const average_profit_loss = hasSellTrades
      ? filteredSellTrades.reduce((acc, trade) => acc + trade.profit_loss, 0) / filteredSellTrades.length
      : "N/A";
    const win_loss_rate = hasSellTrades
      ? (filteredSellTrades.filter(trade => trade.profit_loss > 0).length / filteredSellTrades.length) * 100
      : "N/A";
    const total_profit_loss = hasSellTrades
      ? filteredSellTrades.reduce((acc, trade) => acc + trade.profit_loss, 0)
      : 0;
    const number_of_trades = filteredTrades.length;

    const now = new Date();
    const last7Days = new Date();
    last7Days.setDate(now.getDate() - 7);
    const last30Days = new Date();
    last30Days.setDate(now.getDate() - 30);

    const trades_per_day_last7Days = filteredTrades.reduce((acc, trade) => {
      const tradeDate = new Date(trade.timestamp);
      if (tradeDate >= last7Days) {
        const day = tradeDate.toLocaleDateString();
        acc[day] = (acc[day] || 0) + 1;
      }
      return acc;
    }, {});

    const trades_last30Days = filteredTrades.filter(trade => new Date(trade.timestamp) >= last30Days).length;

    return {
      average_profit_loss,
      win_loss_rate,
      total_profit_loss,
      number_of_trades,
      trades_per_day_last7Days,
      trades_last30Days
    };
  }, []);

  const fetchTrades = useCallback(async () => {
    setLoading(true);
    try {
      const response = await axiosInstance.get('/trades');
      const tradesData = response.data.trades.reverse(); // Show latest trades first
      setInitialTrades(tradesData);
      setTrades(tradesData);
      setStats(calculateStats(tradesData));
    } catch (error) {
      console.error('Error fetching trades:', error);
    } finally {
      setLoading(false);
    }
  }, [calculateStats]);

  const populateFilters = useCallback(async () => {
    try {
      const response = await axiosInstance.get('/trades');
      const brokersSet = new Set(response.data.trades.map(trade => trade.broker));
      const strategiesSet = new Set(response.data.trades.map(trade => trade.strategy));
      setBrokers([...brokersSet]);
      setStrategies([...strategiesSet]);
    } catch (error) {
      console.error('Error populating filters:', error);
    }
  }, []);

  useEffect(() => {
    populateFilters();
    fetchTrades();
  }, [populateFilters, fetchTrades]);

  useEffect(() => {
    filterTrades();
  }, [selectedBrokers, selectedStrategies, selectedOrderTypes, startDate, endDate, filterTrades]);

  useEffect(() => {
    setStats(calculateStats(trades));
  }, [trades, calculateStats]);

  return (
    <div className="container-fluid">
      <h1 className="mt-5">Trades</h1>
      <div className="row mb-3">
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
            options={['buy', 'sell'].map(orderType => ({ value: orderType, label: orderType }))}
            onChange={selectedOptions => setSelectedOrderTypes(selectedOptions.map(option => option.value))}
            placeholder="Select Order Types"
            className="basic-multi-select"
            classNamePrefix="select"
          />
        </div>
      </div>
      <div className="row mb-3">
        <div className="col-md-6">
          <DatePicker
            selected={startDate}
            onChange={(date) => setStartDate(date)}
            selectsStart
            startDate={startDate}
            endDate={endDate}
            placeholderText="Start Date"
            className="form-control"
          />
        </div>
        <div className="col-md-6">
          <DatePicker
            selected={endDate}
            onChange={(date) => setEndDate(date)}
            selectsEnd
            startDate={startDate}
            endDate={endDate}
            placeholderText="End Date"
            className="form-control"
          />
        </div>
      </div>
      {loading ? (
        <div className="text-center my-5">
          <Spinner animation="border" role="status">
            <span className="visually-hidden">Loading...</span>
          </Spinner>
        </div>
      ) : (
        <>
          {stats && (
            <Row className="mb-3">
              <Col md={3}>
                <Card>
                  <Card.Body>
                    <Card.Title>Average P/L</Card.Title>
                    <Card.Text>
                      {typeof stats.average_profit_loss === "number"
                        ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(stats.average_profit_loss)
                        : "N/A"}
                    </Card.Text>
                  </Card.Body>
                </Card>
              </Col>
              <Col md={3}>
                <Card>
                  <Card.Body>
                    <Card.Title>Win/Loss Rate</Card.Title>
                    <Card.Text>
                      {typeof stats.win_loss_rate === "number"
                        ? `${stats.win_loss_rate.toFixed(2)}%`
                        : "N/A"}
                    </Card.Text>
                  </Card.Body>
                </Card>
              </Col>
              <Col md={3}>
                <Card>
                  <Card.Body>
                    <Card.Title>Total Profit/Loss</Card.Title>
                    <Card.Text>
                      {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(stats.total_profit_loss)}
                    </Card.Text>
                  </Card.Body>
                </Card>
              </Col>
              <Col md={3}>
                <Card>
                  <Card.Body>
                    <Card.Title>Number of Trades</Card.Title>
                    <Card.Text>{stats.number_of_trades}</Card.Text>
                  </Card.Body>
                </Card>
              </Col>
              <Col md={3}>
                <Card>
                  <Card.Body>
                    <Card.Title>Trades per Day (Last 7 Days)</Card.Title>
                    <Card.Text>{Object.keys(stats.trades_per_day_last7Days).map(day => (
                      <span key={day}>{day}: {stats.trades_per_day_last7Days[day]}<br/></span>
                    ))}</Card.Text>
                  </Card.Body>
                </Card>
              </Col>
              <Col md={3}>
                <Card>
                  <Card.Body>
                    <Card.Title>Trades in Last 30 Days</Card.Title>
                    <Card.Text>{stats.trades_last30Days}</Card.Text>
                  </Card.Body>
                </Card>
              </Col>
            </Row>
          )}
          <div className="table-responsive">
            <Table striped bordered hover className="trades-table">
              <thead>
                <tr>
                  <th>Broker</th>
                  <th>Strategy</th>
                  <th>Symbol</th>
                  <th>Quantity</th>
                  <th>Price</th>
                  <th>Type</th>
                  <th>Profit/Loss</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade, index) => (
                  <tr key={index}>
                    <td data-label="Broker">{trade.broker}</td>
                    <td data-label="Strategy">{trade.strategy}</td>
                    <td data-label="Symbol">{trade.symbol}</td>
                    <td data-label="Quantity">{trade.quantity}</td>
                    <td data-label="Price">
                      {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(trade.price)}
                    </td>
                    <td data-label="Type">{trade.side}</td>
                    <td data-label="Profit/Loss" className={
                      trade.profit_loss < 0 ? 'text-danger' :
                      trade.profit_loss > 0 ? 'text-success' : ''
                    }>
                      {new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(trade.profit_loss)}
                    </td>
                    <td data-label="Timestamp">{new Date(trade.timestamp).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </div>
        </>
      )}
    </div>
  );
};

export default Trades;
