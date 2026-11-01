FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"
ENV HOICO_ROOT=/srv
ENV PYTHONUNBUFFERED=1

WORKDIR /srv
COPY pyproject.toml README.md ./
COPY src ./src
COPY transformations ./transformations
RUN pip install --no-cache-dir -e . \
    && python -c "from pyspark.sql import SparkSession; from delta import configure_spark_with_delta_pip; b=SparkSession.builder.master('local[1]').appName('prefetch').config('spark.sql.extensions','io.delta.sql.DeltaSparkSessionExtension').config('spark.sql.catalog.spark_catalog','org.apache.spark.sql.delta.catalog.DeltaCatalog').config('spark.driver.host','127.0.0.1').config('spark.ui.enabled','false'); s=configure_spark_with_delta_pip(b).getOrCreate(); s.range(1).write.format('delta').mode('overwrite').save('/tmp/delta-smoke'); s.stop()"

# Python 3.12 removed distutils. PySpark 3.5 still imports it when creating a DataFrame.
RUN apt-get update \
    && apt-get install -y --no-install-recommends procps libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir "setuptools==75.8.0"

COPY docs ./docs
COPY app/data ./app/data
COPY orchestration ./orchestration

CMD ["python", "-m", "hoico.cli", "run-all"]
