# SOAD: System Of A Dow

> NOTE: This is still being developed.

![soad-logo](https://github.com/r0fls/soad/assets/1858004/7369c3af-b4e6-41d9-997c-eaa0b81b969d)


## Features

- Execute multiple strategies simultaneously in isolation
- Supports multiple brokers with a broker agnostic interface
- Options are a first class citizen

## UI Screenshots
![Screen Shot 2024-06-06 at 7 56 38 PM](https://github.com/r0fls/soad/assets/1858004/0e214dd5-c157-47cc-a48f-2ec0f37a7b33)
![Screen Shot 2024-06-06 at 7 55 54 PM](https://github.com/r0fls/soad/assets/1858004/65c4774d-fb49-4452-936c-f5148f958d26)
![Screen Shot 2024-06-06 at 7 56 07 PM](https://github.com/r0fls/soad/assets/1858004/24401792-b0b0-4d2e-b2db-15827cb71b0a)


## Contributing
1. Setup a python virtual environment
```
python -m pyenv python3.12
```
2. Install the required packages:
```
pip install -r requirements.txt
```
3. Initialize the database with fake data:
```
python init_db.py
```
4. Start the frontend (React) server
NOTE: right now you will have to edit this line in `src/axiosInstance.js` file locally to point to `http://localhost:8000`:
https://github.com/r0fls/soad/blob/main/trading-dashboard/src/axiosInstance.js#L4

Then:
```
cd trading-dashboard
yarn start
```
5. Start the python API (in a second terminal window)
```
python main.py --mode api
```
