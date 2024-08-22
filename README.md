# Skywalking Copilot

A [Browser Copilot](https://github.com/abstracta/browser-copilot) that empowers the usage of applications that use [Apache Skywalking](https://skywalking.apache.org/) as observability platform.

Currently, this project only covers some basic scenarios. If you are interested in helping to evolve it we are open to contributions. 

## Requirements

* [devbox](https://www.jetpack.io/devbox)

## Setup

```bash
devbox install && devbox run install
```

Set `OPENAI_API_KEY` with proper value in [.env](./.env)

Start postgres:

```bash
devbox run postgres
```

## Development

To update to latest version of browser-copilot submodule you can use

```bash
devbox run update-git
```

To update to latest dependencies of python:

```bash
devbox run update-python
```

To add new dependencies to python:

```bash
poetry add X
```

To generate new DB migrations due to changes in database.py module:

```bash
devbox run new-migration "description"
```

To run DB migrations against the local database:

```bash
devbox run migrations
```

> the app automatically updates database with migrations when postgres service is started with devbox


## Skywalking Showcase

To try the copilot locally you can try running [Skywalking showcase](https://skywalking.apache.org/docs/skywalking-showcase/next/readme/#quick-start) locally.

The steps to run Skywalking showcase locally:
* clone the repository `https://github.com/apache/skywalking-showcase.git`
* modify `deploy/platform/docker/scripts/docker-compose.agent.yaml` by adding port mapping `9091:80` to frontend service. This allows to access the frontend later on and try the copilot with it. 
* Run on `make deploy.docker FEATURE_FLAGS=single-node,agent`. This wills spin up showcase sample services and skwyalking server, frontend and database. Here is a diagram of deployed infrastrcuture:

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

* Check docker-compose containers status and access `http://localhost:9999` to access the Skywalking frontend. You can now explore information collected by Skywalking on the showcase sample services.

## Run agent in dev mode

```bash
devbox run agent
```

**Note:** The agent is configured by default to connect to `http://localhost:9999` to the Skywalking server and auto trigger the copilot when the application under test is located at `http://localhost:9091`. If you want to try it with another Skywalking instance and application instance change [.env](./.env) file accordingly.

## Run chrome extension in dev mode

```bash
devbox run browser
```

Now if you open a new tab and navigate to the configured application monitored by skywalking (`http://localhost:9091/index.html`) the copilot should automatically activate, and you can start interacting with it.

