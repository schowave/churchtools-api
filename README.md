# Churchtools API

This repository makes it possible to access the churchtools api via User Interface. 

It was created due to the request to show all appointments of [evkila.de](https://www.evkila.de/) on a single pdf file or multiple jpegs.

## What does it do?

### Overview to provide 1..n functionalities
![overview](images/overview.png)

### Select 1..n public calendars for appointments
![appointments](images/calendars.png)

### Generate PDF or JPEG
![generate](images/formatting.png)

### Result
![result](images/result.png)

## Setup

1. Edit the `Dockerfile` file and set it to your churchtools instance.

    ```
    ENV  CHURCHTOOLS_BASE=evkila.church.tools \
         DB_PATH=/app/data/evkila.db
    ```

2. Run the `run.sh` shell script, which will build a docker container and run the container.

    ```
    ./run.sh
    ```

3. Open in Browser

    [http://127.0.0.1:5005/](http://127.0.0.1:5005/)





