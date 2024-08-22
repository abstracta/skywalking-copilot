FROM python:3.12

RUN apt-get update && apt-get install -y netcat-traditional

RUN pip install poetry

RUN poetry config installer.max-workers 10

WORKDIR /usr/src/app
ENV PYTHONPATH "${PYTHONPATH}:/usr/src/app"

COPY pyproject.toml poetry.lock ./

RUN poetry install

COPY docker/entrypoint.sh entrypoint.sh
COPY sample.env .env
COPY alembic.ini alembic.ini
COPY alembic ./alembic
COPY skywalking_copilot ./skywalking_copilot

ADD https://raw.githubusercontent.com/vishnubob/wait-for-it/master/wait-for-it.sh wait-for-it.sh
RUN chmod +x wait-for-it.sh

ENTRYPOINT [ "./entrypoint.sh" ]

EXPOSE 8000

CMD ["poetry", "run", "python", "-m", "skywalking_copilot"]
