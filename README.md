# Physics file serving API 

Flask project with features:

- Ready to ship Flask project template
- **Database migrations** out-of-the-box (uses Alembic)
- Simple setup `make setup && make run` which make local virtualenv isolated environment and doesn't trash your system python.
- Contains `Dockerfile` that allows to setup full Linux environment on any host OS supported by Docker

## How to start

There are two ways. First way is use [`docker`](https://www.docker.com/):

```sh
$ docker build -t flask-smorest-api .
$ docker run -dp 5000:5000 -w /app -v "$(pwd):/app" flask-smorest-api
```

The second way is to run (with some requirements) in the terminal via. Use a vitual environment and install the requirements, then run the app.

```sh
$ pip install -r .\requirements.txt
$ flask run
```

Open http://127.0.0.1:5000/ and **have fun**.


## Requirements

If you never worked with python projects then the simplest way is run project inside Docker. Follow instruction [how to install Docker in your OS](https://docs.docker.com/installation/).

## API structure

The model structure is the following:

    .
    ├── Topic 1
    │   ├── Item 1
    │   │   └── Tag 1
    │   ├── Item 2
    │   └── Item 3
    │   │   ├── Tag 1
    │   │   └── Tag 2

One topic (unique) can have multiple items (unique) that can have multiple tags.


