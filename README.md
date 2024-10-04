# Skywalking Copilot

A [Browser Copilot](https://github.com/abstracta/browser-copilot) that empowers the usage of applications that use [Apache Skywalking](https://skywalking.apache.org/) as an observability platform.

![screenshot](screenshot.png)

Currently, this project only covers some basic scenarios. If you are interested in helping to evolve it, we are open to contributions. 

## Features

* 🤖 Automatic activation of the agent when the configured application is accessed in a browser.
* 🚨 Proactive notifications of live alerts.
* 🕵️‍♂️ Proactive report of traces generated from the application in the active browser tab.
* 🗺️ Provide services topology diagram.
* 🧾 Provide a table of the services and their associated metrics.
* 📉 Generate charts of metrics like response time, error rate, load, Apdex, and message queuing metrics.
* 🤔 Ask any question about displayed information.
* ➕ More to come!

## Requirements

* [devbox](https://www.jetpack.io/devbox)

## Setup

```bash
devbox install && devbox run install
```

Set `OPENAI_API_KEY` with proper value in [.env](./.env)

Start Postgres:

```bash
devbox run postgres
```

## Development

To update to the latest version of the browser-copilot submodule, you can use

```bash
devbox run update-git
```

To update to the latest dependencies of the Python project:

```bash
devbox run update-python
```

To add new dependencies to the Python project:

```bash
poetry add X
```

To generate new DB migrations due to changes in the `database.py` module:

```bash
devbox run new-migration "description"
```

To run DB migrations against the local database:

```bash
devbox run migrations
```

> The app automatically updates the database with migrations when the Postgres service is started with devbox

To update the Skywalking showcase run:

```bash
devbox run update-showcase
```

## Skywalking Showcase

To try the copilot locally, try [Skywalking showcase](https://skywalking.apache.org/docs/skywalking-showcase/next/readme/#quick-start). 

This project already includes a tuned version of the showcase. You can build it with `devbox run update-showcase` and run it with `devbox run showcase`.

This will spin up the Skywalking showcase locally with minimum services and memory required, as well as showcase app frontend access from host and English song names.

Here is a diagram of the deployed infrastructure:

```plantuml
@startuml
!define LOGOS https://raw.githubusercontent.com/plantuml-stdlib/gilbarbara-plantuml-sprites/master/pngs
!define CICON https://raw.githubusercontent.com/plantuml-stdlib/cicon-plantuml-sprites/master/pngs
!define SPRING_LOGO <img:LOGOS/spring-icon.png{scale=0.7}>
!define SKW_LOGO <img:https://skywalking.apache.org/favicons/android-chrome-192x192.png{scale=0.2}>

skinparam DefaultTextAlignment center;

rectangle "Skywalking" {
  agent ui as "UI\nSKW_LOGO"
  agent oap as "OAP\nSKW_LOGO"
  database banyandb
  ui --> oap
  oap --> banyandb
}

rectangle "Sample" {
  agent gateway as "Gateway\nSPRING_LOGO"
  agent songs as "Songs\nSPRING_LOGO"
  database songsdb as "SongsDB"
  agent rcmd as "Recomendations\n<img:LOGOS/flask.png{scale=0.7}>"
  agent app as "App\n<img:LOGOS/nodejs.png{scale=0.7}>"
  agent loadgen as "Loadgen\n<img:LOGOS/selenium.png{scale=0.7}>"
  agent frontend as "Frontend\n<img:LOGOS/react.png{scale=0.7}>"
  queue activemq as "ActiveMQ\n<img:CICON/activemq.png{scale=0.7}>"
  agent rating as "Rating\n<img:LOGOS/go.png{scale=0.7}>"
  
  gateway .> oap
  gateway --> songs
  gateway --> rcmd
  songs .> oap
  songs --> songsdb
  songs --> activemq
  rcmd .> oap
  rcmd --> songs
  rcmd --> rating
  app .> oap
  app --> gateway
  loadgen -> frontend
  frontend .> oap
  frontend --> app
  rating .> oap
  
}
@enduml
```

* To access Skywalking frontend go to `http://localhost:9999`. You can now explore information collected by Skywalking on the showcase sample services.

> To stop the showcase, you can run `devbox run stop-showcase`.

## Run agent in dev mode

```bash
devbox run agent
```

**Note:** The agent is configured by default to connect to `http://localhost:9999` to the Skywalking server and auto-trigger the copilot when the application under test is located at `http://localhost:9091`. If you want to try it with another Skywalking instance and application instance, change the [.env](./.env) file accordingly.

## Run Chrome extension in dev mode

```bash
devbox run browser
```

Now, if you open a new tab and navigate to the configured application monitored by skywalking (`http://localhost:9091/index.html`) the copilot should automatically activate, and you can start interacting with it.
