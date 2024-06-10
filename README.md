# SOAD: System Of A Dow

> NOTE: This is still being developed.

## Features

- Execute multiple strategies simultaneously in isolation
- Supports multiple brokers with a broker agnostic interface
- Options are a first class citizen

## UI Screenshots
![Screen Shot 2024-06-06 at 7 56 38 PM](https://github.com/r0fls/soad/assets/1858004/0e214dd5-c157-47cc-a48f-2ec0f37a7b33)
![Screen Shot 2024-06-06 at 7 55 54 PM](https://github.com/r0fls/soad/assets/1858004/65c4774d-fb49-4452-936c-f5148f958d26)
![Screen Shot 2024-06-06 at 7 56 07 PM](https://github.com/r0fls/soad/assets/1858004/24401792-b0b0-4d2e-b2db-15827cb71b0a)


## TODO


**Code Quality**
- Remove magic strings and numbers
- Add more unit tests
- Review failing unit tests
- Add linting/pysort GHA

**Features**
- Add more brokers
- Add more strategies
- Add position/balance sync worker
- test/develop tastytrade broker

**Misc**
- Documentation
- Postgres helm deploy
- RDS/Cloud Postgres deploy
- Research a TSDB replacement
- Implement async task methodology (use native python?)
- go live on k8s or a VM
- remove ETrade broker
