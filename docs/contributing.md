# Contributing

We welcome contributions to the SOAD project. Here are some ways you can help:

- Report bugs
- Fix issues
- Add new features
- Improve documentation

## How to Contribute
1. Setup a python virtual environment
```bash
python -m pyenv python3.12
```
2. Install the required packages:
```bash
pip install -r requirements.txt
```
3. Initialize the database with fake data:
```bash
python init_db.py
```
4. Start the frontend (React) server
NOTE: right now you will have to edit this line in `src/axiosInstance.js` file locally to point to `http://localhost:8000`:
https://github.com/r0fls/soad/blob/main/trading-dashboard/src/axiosInstance.js#L4

Then:
```bash
cd trading-dashboard
yarn start
```
5. Start the python API (in a second terminal window)
```bash
python main.py --mode api

```
## Code of Conduct

If you have any problems getting, feel free to create a Github issue.

Please follow our [Code of Conduct](https://github.com/r0fls/soad/blob/main/CODE_OF_CONDUCT.md).
