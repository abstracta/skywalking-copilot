#!/bin/bash

set -e

if [[ $DB_URL == "postgresql"* ]]; then
  SERVER="${DB_URL##*@}"
  SERVER="${SERVER%%/*}"
  if [[ $SERVER != *":"* ]]; then
    SERVER="${SERVER}:5432"
  fi
  /usr/src/app/wait-for-it.sh -t 60 "${SERVER}"
fi

exec "$@"
