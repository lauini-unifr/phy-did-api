# Physics file serving API 

Flask project with features:

- Ready to ship Flask project template
- **Database migrations** out-of-the-box (uses Alembic)
- Simple setup `make setup && make run` which make local virtualenv isolated environment and doesn't trash your system python.

## How to start

Use a vitual environment and install the requirements, then run the app.

```sh
$ pip install -r .\requirements.txt
$ flask run
```

Open http://127.0.0.1:5000/ and **have fun**.


## Requirements

You need a installed Latex version on your device. On debian use
```sh
$ sudo apt-get install texlive-full
```
Or cover it by installing MikTex or an other Compiler.


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



# How to maintain the server for a new git pull

Move to the project folder, pull and merge:

```sh
$ cd phy-did-api
$ git pull
$ git merge
```

Restart the flask server:
```sh
$ systemctl restart phy-did-api
```



# How to setup the server

Requirements: A debian 12 server and root privilges.

## Step 1: Install Required Dependencies 

First, you will need to install Python and other required dependencies to your system. You can install all of them using the following command: 

```sh
$ apt-get install python3-pip libssl-dev libffi-dev python3-dev build-essential python3-setuptools -y
``` 

Once all the packages are installed, install a Python virtual environment package with the following command: 
```sh
$ apt-get install python3-venv -y 
```

Next, upgrade the PIP to the latest version using the following command: 

```sh
$ pip3 install --upgrade pip
```

You'll also need to install the Nginx webserver to serve the Python application. You can install it using the following command: 

```sh
$ apt-get install nginx -y
```


In this section, we'll install Flask and checkout the Github repo. 

First, create a directory for your application using the following command: 

```sh
$ mkdir ~/phy-did-api 
```

Next, change the directory to your application and create a Python virtual environment: 

```sh
$ cd ~/phy-did-api
$ python3 -m venv venv
```

To go on, activate the virtual environment with the following command: 

```sh
$ source venv/bin/activate
```

Next, install Flask and Gunicorn with the following command: 

```sh
$ pip install wheel
$ pip install gunicorn flask
```

Now clone the Github repo to the server.

```sh
$ apt-get install git
$ git clone url
```

Run your application with the following command: 

```sh
$ cd ~/phy-did-api/
$ pip install -r requirements.txt
$ flask run
```

You should see the following output:

```sh
* Serving Flask app "pyh-did-api" (lazy loading)
 * Environment: production
   WARNING: This is a development server. Do not use it in a production deployment.
   Use a production WSGI server instead.
 * Debug mode: off
 * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)

Press "CTRL+C" to stop the application.
Configure Gunicorn to Run Your Application
```

## Configure Gunicorn to Run Your Application

In this section, we will create a wsgi file and configure Gunicorn to run your Python application. 

First, create a wsgi.py file: 

```sh
$  nano ~/phy-did-api/wsgi.py
```

Add the following lines: 

```sh
from app import create_app

if __name__ == "__main__":
	create_app = create_app()
	create_app.run()
else:
	gunicorn_app = create_app()
```

Save and close the file then run your application with Gunicorn: 

```sh
$ cd ~/phy-did-api/
$ gunicorn --bind 0.0.0.0:5000 wsgi:app
```

You should see the following output:

```sh
(venv) root@debian10:~/phy-did-api# gunicorn --bind 0.0.0.0:5000 wsgi:app
[2021-04-21 07:25:03 +0000] [8483] [INFO] Starting gunicorn 20.1.0
[2021-04-21 07:25:03 +0000] [8483] [INFO] Listening at: http://0.0.0.0:5000 (8483)
[2021-04-21 07:25:03 +0000] [8483] [INFO] Using worker: sync
[2021-04-21 07:25:03 +0000] [8486] [INFO] Booting worker with pid: 8486
```

Press "CTRL+C" to stop the application. 

Next, deactivate your Python virtual environment with the following command: 

```sh
$ deactivate
```

## Create a Systemd Service File for Python Application

Next, you will need to create a systemd service file to manage the Python application. 

You can create it with the following command: 

```sh
$ nano /etc/systemd/system/phy-did-api.service
```

Add the following lines:

```sh
[Unit]
Description=Gunicorn instance to serve Flask
After=network.target

[Service]
User=root
Group=www-data
WorkingDirectory=/root/phy-did-api
Environment="PATH=/root/venv/bin:/usr/bin"
ExecStart=/root/venv/bin/gunicorn --bind 0.0.0.0:5000 wsgi:gunicorn_app

[Install]
WantedBy=multi-user.target
```

Save and close the file then set proper ownership and permission with the following command: 

```sh
$ chown -R root:www-data /root/phy-did-api
$ chmod -R 775 /root/phy-did-api
```

Next, reload the systemd daemon with the following command: 

```sh
$ systemctl daemon-reload
```

Next, start the flask service and enable it to start at system reboot: 

```sh
$ systemctl start phy-did-api
$ systemctl enable phy-did-api
```

Next, verify the status of the flask with the following command: 

```sh
$ systemctl status phy-did-api
```

You should see the following output:

```sh
● phy-did-api.service - Gunicorn instance to serve Flask
   Loaded: loaded (/etc/systemd/system/phy-did-api.service; disabled; vendor preset: enabled)
   Active: active (running) since Wed 2021-04-21 07:25:51 UTC; 4s ago
 Main PID: 8506 (gunicorn)
    Tasks: 2 (limit: 2359)
   Memory: 26.0M
   CGroup: /system.slice/phy-did-api.service
           ├─8506 /root/venv/bin/python3 /root/venv/bin/gunicorn --bind 0.0.0.0:5000 wsgi:app
           └─8508 /root/venv/bin/python3 /root/venv/bin/gunicorn --bind 0.0.0.0:5000 wsgi:app

Apr 21 07:25:51 debian10 systemd[1]: Started Gunicorn instance to serve Flask.
Apr 21 07:25:51 debian10 gunicorn[8506]: [2021-04-21 07:25:51 +0000] [8506] [INFO] Starting gunicorn 20.1.0
Apr 21 07:25:51 debian10 gunicorn[8506]: [2021-04-21 07:25:51 +0000] [8506] [INFO] Listening at: http://0.0.0.0:5000 (8506)
Apr 21 07:25:51 debian10 gunicorn[8506]: [2021-04-21 07:25:51 +0000] [8506] [INFO] Using worker: sync
Apr 21 07:25:51 debian10 gunicorn[8506]: [2021-04-21 07:25:51 +0000] [8508] [INFO] Booting worker with pid: 8508

```

## Configure Nginx to Serve Python Application 

Next, you will need to create an Nginx virtual host configuration file to serve Python application. 

```sh
$ nano /etc/nginx/conf.d/phy-did-api.conf
```

Add the following lines:

```sh
server {
    listen 80;
    server_name phy-did-api.com;

    location / {
        include proxy_params;
        proxy_pass  http://0.0.0.0:5000;
    }
}
```

Save and close the file then restart the Nginx to apply the configuration changes: 

```sh
$ systemctl restart nginx
```